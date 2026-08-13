<script setup>
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  Check,
  ChevronDown,
  ChevronUp,
  Eye,
  FlaskConical,
  Play,
  Plus,
  RefreshCw,
  Rocket,
  RotateCcw,
  Trash2
} from 'lucide-vue-next'

import { qualityApi } from '@/apis/quality_api'

const agents = ref([])
const selectedAgent = ref('')
const samples = ref([])
const candidates = ref([])
const experiments = ref([])
const experiment = ref(null)
const selectedCandidateId = ref('')
const loading = ref(false)
const agentLoading = ref(false)
const action = ref('')
const error = ref('')
const showAdvanced = ref(false)
const sampleForm = ref({ input_text: '', expected_output: '' })
const candidateForm = ref({ system_prompt: '', model_spec: '', skill_slugs: '', change_summary: '' })

const normalizeAgent = (agent) => {
  const id = agent?.agent_id || agent?.slug || agent?.id
  return id ? { ...agent, id, agent_id: agent?.agent_id || id, slug: agent?.slug || id } : agent
}

const availableAgents = computed(() => agents.value)
const selectedAgentItem = computed(() => availableAgents.value.find((agent) => agent.id === selectedAgent.value))
const sampleMap = computed(() => new Map(samples.value.map((sample) => [sample.id, sample])))
const candidateOptions = computed(() =>
  candidates.value.map((candidate) => ({
    value: candidate.id,
    label: `v${candidate.version} · ${candidate.change_summary || '未填写变更说明'}`
  }))
)
const selectedCandidate = computed(() =>
  candidates.value.find((candidate) => candidate.id === selectedCandidateId.value)
)
const canRunComparison = computed(() => Boolean(samples.value.length && selectedCandidateId.value))
const scoreDelta = computed(() => experiment.value?.summary?.delta)

const withTimeout = (promise, messageText, timeout = 10000) => {
  let timer
  const timeoutPromise = new Promise((_, reject) => {
    timer = window.setTimeout(() => reject(new Error(messageText)), timeout)
  })
  return Promise.race([promise, timeoutPromise]).finally(() => window.clearTimeout(timer))
}

const statusText = (status) => ({
  queued: '等待运行', running: '运行中', completed: '已完成', failed: '失败',
  draft: '草稿', approved: '已批准', published: '已发布', superseded: '已替代', rolled_back: '已回滚'
}[status] || status || '未知')

const statusClass = (status) => ({
  completed: 'success', published: 'success', approved: 'info', running: 'info',
  queued: 'warning', draft: 'neutral', failed: 'error', rolled_back: 'warning', superseded: 'neutral'
}[status] || 'neutral')

const formatDate = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

const sampleLabel = (sampleId) => sampleMap.value.get(sampleId)?.input_text || '样本已不可用'
const variantText = (variant) => variant === 'candidate' ? '候选版本' : '当前版本'

const loadExperimentDetail = async (item, showError = true) => {
  if (!item) {
    experiment.value = null
    return
  }
  try {
    const response = await qualityApi.getExperiment(item.id)
    experiment.value = { ...response.experiment, results: response.results || [] }
  } catch (err) {
    if (showError) message.error(err.message || '加载实验详情失败')
    experiment.value = item
  }
}

const load = async () => {
  if (!selectedAgent.value) return
  loading.value = true
  error.value = ''
  try {
    const [sampleResponse, candidateResponse, experimentResponse] = await withTimeout(
      Promise.all([
        qualityApi.listSamples(selectedAgent.value),
        qualityApi.listCandidates(selectedAgent.value),
        qualityApi.listExperiments(selectedAgent.value)
      ]),
      '加载质量数据超时，请检查 API 服务'
    )
    samples.value = sampleResponse.samples || []
    candidates.value = candidateResponse.candidates || []
    experiments.value = experimentResponse.experiments || []
    if (!candidates.value.some((item) => item.id === selectedCandidateId.value)) {
      selectedCandidateId.value = candidates.value[0]?.id || ''
    }
    const current = experiments.value.find((item) => item.id === experiment.value?.id)
    await loadExperimentDetail(current || experiments.value[0], false)
  } catch (err) {
    error.value = err.message || '加载质量数据失败'
  } finally {
    loading.value = false
  }
}

const loadAgents = async () => {
  agentLoading.value = true
  error.value = ''
  try {
    const response = await withTimeout(qualityApi.listAgents(), '加载智能体超时，请检查登录状态或 API 服务')
    agents.value = (response.agents || []).map(normalizeAgent)
    const current = availableAgents.value.find((agent) => agent.id === selectedAgent.value)
    selectedAgent.value = current?.id || availableAgents.value[0]?.id || ''
    if (selectedAgent.value) await load()
  } catch (err) {
    error.value = err.message || '加载智能体失败'
  } finally {
    agentLoading.value = false
  }
}

const createSample = async () => {
  if (!sampleForm.value.input_text.trim()) return
  action.value = 'sample'
  try {
    await qualityApi.createSample({ agent_slug: selectedAgent.value, ...sampleForm.value })
    sampleForm.value = { input_text: '', expected_output: '' }
    await load()
    message.success('测试样本已加入')
  } catch (err) {
    message.error(err.message || '添加测试样本失败')
  } finally {
    action.value = ''
  }
}

const createCandidate = async () => {
  const config = {}
  if (candidateForm.value.system_prompt.trim()) config.system_prompt = candidateForm.value.system_prompt.trim()
  if (candidateForm.value.model_spec.trim()) config.model_spec = candidateForm.value.model_spec.trim()
  const skillSlugs = candidateForm.value.skill_slugs.split(',').map((item) => item.trim()).filter(Boolean)
  if (skillSlugs.length) config.skill_slugs = skillSlugs
  if (!Object.keys(config).length) {
    message.warning('请至少填写候选 Prompt、模型或 Skill 中的一项')
    return
  }
  action.value = 'candidate'
  try {
    const response = await qualityApi.createCandidate({
      agent_slug: selectedAgent.value,
      change_summary: candidateForm.value.change_summary,
      config
    })
    candidateForm.value = { system_prompt: '', model_spec: '', skill_slugs: '', change_summary: '' }
    selectedCandidateId.value = response.candidate.id
    await load()
    message.success('候选版本已保存')
  } catch (err) {
    message.error(err.message || '创建候选版本失败')
  } finally {
    action.value = ''
  }
}

const runReplay = async (candidateId = null) => {
  action.value = 'experiment'
  try {
    const created = await qualityApi.createExperiment({ agent_slug: selectedAgent.value, candidate_id: candidateId })
    const result = await qualityApi.runExperiment(created.experiment.id)
    await load()
    await loadExperimentDetail(result.experiment)
    message.success(result.experiment.status === 'completed' ? '回放对比已完成' : '回放已结束，请查看失败原因')
  } catch (err) {
    message.error(err.message || '运行回放失败')
  } finally {
    action.value = ''
  }
}

const updateCandidate = async (candidate, operation) => {
  action.value = `${operation}-${candidate.id}`
  try {
    const response = await qualityApi[operation](candidate.id)
    const index = candidates.value.findIndex((item) => item.id === candidate.id)
    if (index >= 0) candidates.value[index] = response.candidate
    message.success(operation === 'approveCandidate' ? '候选版本已批准' : operation === 'publishCandidate' ? '候选版本已发布' : '候选版本已回滚')
  } catch (err) {
    message.error(err.message || '操作失败')
  } finally {
    action.value = ''
  }
}

const showExperiment = async (item) => {
  action.value = `details-${item.id}`
  await loadExperimentDetail(item)
  action.value = ''
}

const deleteExperiment = async (item) => {
  action.value = `delete-${item.id}`
  try {
    await qualityApi.deleteExperiment(item.id)
    experiments.value = experiments.value.filter((experimentItem) => experimentItem.id !== item.id)
    if (experiment.value?.id === item.id) await loadExperimentDetail(experiments.value[0], false)
    message.success('实验记录已删除')
  } catch (err) {
    message.error(err.message || '删除实验记录失败')
  } finally {
    action.value = ''
  }
}

defineExpose({
  loading: computed(() => agentLoading.value || loading.value),
  stats: computed(() => ({ samples: samples.value.length, candidates: candidates.value.length, experiments: experiments.value.length }))
})

onMounted(loadAgents)
</script>

<template>
  <div class="quality-loop-panel">
    <div class="quality-toolbar">
      <div>
        <h2>Agent 版本评测</h2>
        <p>使用同一组问题，对比当前配置与候选配置的回答质量。</p>
      </div>
      <div class="quality-toolbar-actions">
        <span class="field-label">评测对象</span>
        <a-select
          v-model:value="selectedAgent"
          class="quality-agent-select"
          :options="availableAgents.map((agent) => ({ value: agent.id, label: agent.name || agent.id }))"
          placeholder="选择智能体"
          @change="load"
        />
        <a-button class="lucide-icon-btn" :disabled="agentLoading" :loading="agentLoading || loading" title="刷新" @click="loadAgents">
          <RefreshCw :size="15" />
        </a-button>
      </div>
    </div>

    <div v-if="agentLoading" class="quality-loading-state"><a-spin /></div>
    <a-alert v-else-if="error" type="error" :message="error" show-icon />
    <a-empty v-else-if="!selectedAgentItem" description="当前没有可管理的智能体" />
    <template v-else>
      <div class="workflow-grid">
        <section class="workflow-step">
          <div class="step-heading">
            <span class="step-index">1</span>
            <div><h3>准备测试问题</h3><p>期望答案用于自动评分，可填写关键事实或固定短语。</p></div>
            <span class="step-count">{{ samples.length }} 条</span>
          </div>
          <label class="form-label">测试问题</label>
          <a-textarea v-model:value="sampleForm.input_text" :rows="3" placeholder="例如：请用一句话说明退款条件" />
          <label class="form-label">期望答案 <small>可选</small></label>
          <a-textarea v-model:value="sampleForm.expected_output" :rows="2" placeholder="例如：购买后 7 天内可退款" />
          <a-button type="primary" :disabled="!sampleForm.input_text.trim()" :loading="action === 'sample'" @click="createSample">
            <Plus :size="14" />加入测试集
          </a-button>
          <div v-if="samples.length" class="compact-list">
            <div v-for="sample in samples.slice(0, 4)" :key="sample.id" class="compact-row">
              <span :title="sample.input_text">{{ sample.input_text }}</span>
              <small>{{ sample.expected_output ? '已设置答案' : '只检查是否回答' }}</small>
            </div>
          </div>
          <p v-else class="inline-empty">先加入至少一条问题，才能运行评测。</p>
        </section>

        <section class="workflow-step">
          <div class="step-heading">
            <span class="step-index">2</span>
            <div><h3>创建候选版本</h3><p>先调整 Prompt；模型和 Skill 仅在需要时覆盖。</p></div>
            <span class="step-count">{{ candidates.length }} 个</span>
          </div>
          <label class="form-label">候选 Prompt</label>
          <a-textarea v-model:value="candidateForm.system_prompt" :rows="3" placeholder="填写希望验证的新指令" />
          <label class="form-label">变更说明</label>
          <a-input v-model:value="candidateForm.change_summary" placeholder="例如：要求结论附带来源" />
          <button class="advanced-toggle" type="button" @click="showAdvanced = !showAdvanced">
            <component :is="showAdvanced ? ChevronUp : ChevronDown" :size="14" />
            {{ showAdvanced ? '收起高级设置' : '高级设置' }}
          </button>
          <div v-if="showAdvanced" class="advanced-fields">
            <div><label class="form-label">候选模型标识</label><a-input v-model:value="candidateForm.model_spec" placeholder="沿用当前模型则留空" /></div>
            <div><label class="form-label">Skill slug</label><a-input v-model:value="candidateForm.skill_slugs" placeholder="多个 Skill 使用逗号分隔" /></div>
          </div>
          <a-button :disabled="!selectedAgent" :loading="action === 'candidate'" @click="createCandidate">
            <FlaskConical :size="14" />保存候选版本
          </a-button>
          <div v-if="candidates.length" class="candidate-list">
            <div v-for="candidate in candidates" :key="candidate.id" class="candidate-row" :class="{ selected: selectedCandidateId === candidate.id }" @click="selectedCandidateId = candidate.id">
              <div class="candidate-copy">
                <strong>v{{ candidate.version }}</strong>
                <span :title="candidate.change_summary">{{ candidate.change_summary || '未填写变更说明' }}</span>
              </div>
              <span class="status-tag" :class="statusClass(candidate.status)">{{ statusText(candidate.status) }}</span>
              <div class="candidate-actions" @click.stop>
                <a-button v-if="candidate.status === 'draft'" size="small" type="text" :loading="action === `approveCandidate-${candidate.id}`" title="批准" @click="updateCandidate(candidate, 'approveCandidate')"><Check :size="14" /></a-button>
                <a-button v-if="candidate.status === 'approved'" size="small" type="text" :loading="action === `publishCandidate-${candidate.id}`" title="发布" @click="updateCandidate(candidate, 'publishCandidate')"><Rocket :size="14" /></a-button>
                <a-button v-if="candidate.status === 'published'" size="small" type="text" :loading="action === `rollbackCandidate-${candidate.id}`" title="回滚" @click="updateCandidate(candidate, 'rollbackCandidate')"><RotateCcw :size="14" /></a-button>
              </div>
            </div>
          </div>
        </section>

        <section class="workflow-step run-step">
          <div class="step-heading">
            <span class="step-index">3</span>
            <div><h3>运行对比</h3><p>每条问题会分别调用当前版本和候选版本。</p></div>
          </div>
          <label class="form-label">要评测的候选版本</label>
          <a-select v-model:value="selectedCandidateId" :options="candidateOptions" placeholder="请先创建候选版本" />
          <div v-if="selectedCandidate" class="selection-summary">
            <span>v{{ selectedCandidate.version }}</span>
            <span>{{ samples.length }} 条问题</span>
            <span>预计 {{ samples.length * 2 }} 次 Agent 调用</span>
          </div>
          <a-button type="primary" :disabled="!canRunComparison" :loading="action === 'experiment'" @click="runReplay(selectedCandidateId)">
            <Play :size="14" />运行基线与候选对比
          </a-button>
          <a-button :disabled="!samples.length || action === 'experiment'" @click="runReplay()">仅检查当前版本</a-button>
        </section>
      </div>

      <section class="result-section">
        <div class="section-heading">
          <div><h3>实验结果</h3><p>分数按期望答案匹配计算：完全一致 100，包含 70，不包含 20，无输出 0。</p></div>
          <span v-if="experiment" class="status-tag" :class="statusClass(experiment.status)">{{ statusText(experiment.status) }}</span>
        </div>
        <a-empty v-if="!experiment" description="运行一次对比后，这里会显示分数和逐条回答" />
        <template v-else>
          <a-alert v-if="experiment.status === 'failed'" type="error" :message="experiment.error_message || '实验运行失败'" show-icon />
          <div class="score-comparison">
            <div><small>当前版本</small><strong>{{ experiment.baseline_score ?? '-' }}</strong></div>
            <span v-if="experiment.candidate_id" class="score-arrow">→</span>
            <div v-if="experiment.candidate_id"><small>候选版本</small><strong>{{ experiment.candidate_score ?? '-' }}</strong></div>
            <div v-if="experiment.candidate_id" class="delta-score" :class="{ positive: scoreDelta > 0, negative: scoreDelta < 0 }">
              <small>分差</small><strong>{{ scoreDelta == null ? '-' : `${scoreDelta > 0 ? '+' : ''}${scoreDelta}` }}</strong>
            </div>
          </div>
          <div v-if="experiment.results?.length" class="result-table-wrap">
            <a-table :data-source="experiment.results" :pagination="false" size="small" row-key="id">
              <a-table-column key="sample_id" title="测试问题" :width="260">
                <template #default="{ record }"><span class="cell-ellipsis" :title="sampleLabel(record.sample_id)">{{ sampleLabel(record.sample_id) }}</span></template>
              </a-table-column>
              <a-table-column key="variant" title="版本" :width="100">
                <template #default="{ record }">{{ variantText(record.variant) }}</template>
              </a-table-column>
              <a-table-column key="score" data-index="score" title="评分" :width="72" />
              <a-table-column key="judge_reason" data-index="judge_reason" title="判定" :width="180" />
              <a-table-column key="output" title="回答">
                <template #default="{ record }"><span class="cell-ellipsis" :title="record.output">{{ record.output || '无输出' }}</span></template>
              </a-table-column>
            </a-table>
          </div>
        </template>
      </section>

      <section class="history-section">
        <div class="section-heading"><div><h3>实验历史</h3><p>删除实验会同时删除逐条结果，不影响样本、候选版本和 Agent 配置。</p></div><span>{{ experiments.length }} 条</span></div>
        <a-empty v-if="!experiments.length" description="暂无实验历史" />
        <div v-else class="history-list">
          <div v-for="item in experiments" :key="item.id" class="history-row" :class="{ active: experiment?.id === item.id }">
            <span class="status-tag" :class="statusClass(item.status)">{{ statusText(item.status) }}</span>
            <div class="history-main"><strong>{{ item.candidate_id ? '基线 vs 候选' : '仅当前版本' }}</strong><small>{{ formatDate(item.created_at) }} · {{ item.sample_count }} 条问题</small></div>
            <div class="history-scores"><span>当前 {{ item.baseline_score ?? '-' }}</span><span v-if="item.candidate_id">候选 {{ item.candidate_score ?? '-' }}</span><strong v-if="item.summary?.delta != null">{{ item.summary.delta > 0 ? '+' : '' }}{{ item.summary.delta }}</strong></div>
            <div class="history-actions">
              <a-button class="lucide-icon-btn" type="text" :loading="action === `details-${item.id}`" title="查看结果" @click="showExperiment(item)"><Eye :size="15" /></a-button>
              <a-popconfirm title="删除这条实验记录？" ok-text="删除" cancel-text="取消" @confirm="deleteExperiment(item)">
                <a-button class="lucide-icon-btn danger" type="text" :disabled="item.status === 'running'" :loading="action === `delete-${item.id}`" title="删除实验"><Trash2 :size="15" /></a-button>
              </a-popconfirm>
            </div>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped lang="less">
.quality-loop-panel { padding: 20px var(--page-padding) 40px; }
.quality-toolbar, .quality-toolbar-actions, .step-heading, .section-heading, .candidate-row, .candidate-actions, .selection-summary, .score-comparison, .history-row, .history-actions { display: flex; align-items: center; }
.quality-toolbar { justify-content: space-between; gap: 20px; margin-bottom: 20px; }
.quality-toolbar h2, .quality-toolbar p, h3, .section-heading p { margin: 0; }
.quality-toolbar h2 { font-size: 18px; }
.quality-toolbar p, .step-heading p, .section-heading p { margin-top: 4px; color: var(--gray-500); font-size: 12px; }
.quality-toolbar-actions { gap: 8px; }
.field-label, .form-label { color: var(--gray-700); font-size: 12px; font-weight: 500; }
.form-label small { color: var(--gray-400); font-weight: 400; }
.quality-agent-select { width: 220px; }
.workflow-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(250px, .72fr); border: 1px solid var(--gray-150); border-radius: 8px; overflow: hidden; }
.workflow-step { display: flex; flex-direction: column; gap: 9px; min-width: 0; padding: 18px; background: var(--gray-0); border-right: 1px solid var(--gray-150); }
.workflow-step:last-child { border-right: 0; }
.run-step { background: var(--gray-10); }
.step-heading { align-items: flex-start; gap: 10px; min-height: 54px; }
.step-heading > div { min-width: 0; flex: 1; }
.step-heading h3, .section-heading h3 { font-size: 15px; color: var(--gray-900); }
.step-index { display: grid; place-items: center; width: 24px; height: 24px; flex: 0 0 24px; border-radius: 5px; background: var(--gray-100); color: var(--gray-700); font-size: 12px; font-weight: 600; }
.step-count { color: var(--gray-500); font-size: 12px; white-space: nowrap; }
.compact-list, .candidate-list, .history-list { display: flex; flex-direction: column; }
.compact-list, .candidate-list { margin-top: 3px; border-top: 1px solid var(--gray-100); }
.candidate-list { max-height: 220px; overflow-y: auto; }
.compact-row { display: flex; justify-content: space-between; gap: 8px; padding: 8px 2px; border-bottom: 1px solid var(--gray-100); font-size: 12px; }
.compact-row span, .candidate-copy span, .cell-ellipsis { display: block; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.compact-row small, .inline-empty { flex-shrink: 0; color: var(--gray-500); font-size: 12px; }
.inline-empty { margin: 5px 0 0; }
.advanced-toggle { display: inline-flex; align-items: center; align-self: flex-start; gap: 4px; padding: 2px 0; border: 0; background: none; color: var(--gray-600); font-size: 12px; cursor: pointer; }
.advanced-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 10px; border: 1px solid var(--gray-100); border-radius: 6px; background: var(--gray-10); }
.advanced-fields > div { display: flex; flex-direction: column; gap: 5px; min-width: 0; }
.candidate-row { gap: 8px; min-height: 44px; padding: 7px 5px; border-bottom: 1px solid var(--gray-100); cursor: pointer; }
.candidate-row:hover, .candidate-row.selected { background: var(--main-10); }
.candidate-copy { display: grid; grid-template-columns: 28px minmax(0, 1fr); align-items: center; gap: 6px; min-width: 0; flex: 1; }
.candidate-copy span { color: var(--gray-600); font-size: 12px; }
.candidate-actions { min-width: 30px; justify-content: flex-end; }
.selection-summary { flex-wrap: wrap; gap: 6px; padding: 10px; border: 1px solid var(--gray-100); border-radius: 6px; background: var(--gray-0); }
.selection-summary span { padding-right: 7px; border-right: 1px solid var(--gray-150); color: var(--gray-600); font-size: 12px; }
.selection-summary span:last-child { border-right: 0; }
.result-section, .history-section { margin-top: 18px; padding-top: 18px; border-top: 1px solid var(--gray-150); }
.section-heading { justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.status-tag { display: inline-flex; align-items: center; justify-content: center; min-width: 52px; padding: 3px 7px; border-radius: 999px; font-size: 12px; white-space: nowrap; }
.status-tag.success { background: var(--color-success-50); color: var(--color-success-700); }
.status-tag.error { background: var(--color-error-50); color: var(--color-error-700); }
.status-tag.warning { background: var(--color-warning-50); color: var(--color-warning-900); }
.status-tag.info { background: var(--color-info-50); color: var(--color-info-700); }
.status-tag.neutral { background: var(--gray-100); color: var(--gray-600); }
.score-comparison { justify-content: center; gap: 18px; min-height: 96px; margin-bottom: 14px; border: 1px solid var(--gray-150); border-radius: 8px; background: var(--gray-10); }
.score-comparison > div { display: flex; min-width: 96px; flex-direction: column; align-items: center; }
.score-comparison small { color: var(--gray-500); font-size: 12px; }
.score-comparison strong { color: var(--gray-900); font-size: 28px; line-height: 34px; }
.score-arrow { color: var(--gray-400); font-size: 20px; }
.delta-score { padding-left: 18px; border-left: 1px solid var(--gray-150); }
.delta-score.positive strong { color: var(--color-success-700); }
.delta-score.negative strong { color: var(--color-error-700); }
.result-table-wrap { overflow-x: auto; }
.history-list { border: 1px solid var(--gray-150); border-radius: 8px; overflow: hidden; }
.history-row { min-height: 58px; gap: 12px; padding: 10px 12px; border-bottom: 1px solid var(--gray-100); }
.history-row:last-child { border-bottom: 0; }
.history-row.active { background: var(--main-10); }
.history-main { display: flex; min-width: 0; flex: 1; flex-direction: column; }
.history-main strong { color: var(--gray-800); font-size: 13px; }
.history-main small { color: var(--gray-500); font-size: 12px; }
.history-scores { display: flex; align-items: center; gap: 12px; color: var(--gray-600); font-size: 12px; }
.history-scores strong { min-width: 32px; color: var(--gray-900); }
.history-actions { gap: 2px; }
.danger { color: var(--color-error-700); }
.quality-loading-state { display: flex; align-items: center; justify-content: center; min-height: 260px; }
@media (max-width: 1100px) {
  .workflow-grid { grid-template-columns: 1fr 1fr; }
  .run-step { grid-column: 1 / -1; border-top: 1px solid var(--gray-150); }
  .workflow-step:nth-child(2) { border-right: 0; }
}
@media (max-width: 760px) {
  .quality-toolbar, .quality-toolbar-actions { align-items: stretch; flex-direction: column; }
  .quality-agent-select { width: 100%; }
  .workflow-grid { grid-template-columns: 1fr; }
  .workflow-step { border-right: 0; border-bottom: 1px solid var(--gray-150); }
  .run-step { grid-column: auto; border-top: 0; }
  .advanced-fields { grid-template-columns: 1fr; }
  .history-row { align-items: flex-start; flex-wrap: wrap; }
  .history-scores { order: 3; width: 100%; }
  .score-comparison { gap: 10px; }
  .score-comparison > div { min-width: 70px; }
}
</style>
