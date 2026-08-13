<script setup>
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { Check, Eye, FlaskConical, Play, Plus, RotateCcw, Rocket, RefreshCw } from 'lucide-vue-next'

import { qualityApi } from '@/apis/quality_api'

const agents = ref([])
const selectedAgent = ref('')
const samples = ref([])
const candidates = ref([])
const experiment = ref(null)
const experiments = ref([])
const loading = ref(false)
const agentLoading = ref(false)
const action = ref('')
const error = ref('')
const sampleForm = ref({ input_text: '', expected_output: '' })
const candidateForm = ref({ system_prompt: '', model_spec: '', skill_slugs: '', change_summary: '' })

const normalizeAgent = (agent) => {
  const id = agent?.agent_id || agent?.slug || agent?.id
  return id
    ? {
        ...agent,
        id,
        agent_id: agent?.agent_id || id,
        slug: agent?.slug || id
      }
    : agent
}

const availableAgents = computed(() => agents.value)
const selectedAgentItem = computed(() => availableAgents.value.find((agent) => agent.id === selectedAgent.value))

const withTimeout = (promise, messageText, timeout = 10000) => {
  let timer
  const timeoutPromise = new Promise((_, reject) => {
    timer = window.setTimeout(() => reject(new Error(messageText)), timeout)
  })

  return Promise.race([promise, timeoutPromise]).finally(() => window.clearTimeout(timer))
}

const loadAgents = async () => {
  agentLoading.value = true
  error.value = ''
  try {
    const response = await withTimeout(qualityApi.listAgents(), '加载智能体超时，请检查登录状态或 API 服务')
    agents.value = (response.agents || []).map(normalizeAgent)
    setDefaultAgent()
  } catch (err) {
    error.value = err.message || '加载智能体失败'
  } finally {
    agentLoading.value = false
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
    experiment.value = experiments.value[0] || null
  } catch (err) {
    error.value = err.message || '加载质量数据失败'
  } finally {
    loading.value = false
  }
}

const createSample = async () => {
  if (!sampleForm.value.input_text.trim()) return
  action.value = 'sample'
  try {
    await qualityApi.createSample({ agent_slug: selectedAgent.value, ...sampleForm.value })
    sampleForm.value = { input_text: '', expected_output: '' }
    await load()
    message.success('Replay 样本已加入')
  } catch (err) {
    message.error(err.message || '添加样本失败')
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
    message.warning('请至少填写一项 Prompt、模型或 Skill 变更')
    return
  }
  action.value = 'candidate'
  try {
    await qualityApi.createCandidate({
      agent_slug: selectedAgent.value,
      change_summary: candidateForm.value.change_summary,
      config
    })
    candidateForm.value = { system_prompt: '', model_spec: '', skill_slugs: '', change_summary: '' }
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
    experiment.value = result.experiment
    await load()
    message.success('回放评测已完成')
  } catch (err) {
    message.error(err.message || '回放评测失败')
  } finally {
    action.value = ''
  }
}

const updateCandidate = async (candidate, operation) => {
  action.value = candidate.id
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

const setDefaultAgent = () => {
  const currentAgent = availableAgents.value.find((agent) => agent.id === selectedAgent.value)
  selectedAgent.value = currentAgent?.id || availableAgents.value[0]?.id || ''
  if (selectedAgent.value) load()
}

const showExperiment = async (item) => {
  action.value = `details-${item.id}`
  try {
    const response = await qualityApi.getExperiment(item.id)
    experiment.value = { ...response.experiment, results: response.results || [] }
  } catch (err) {
    message.error(err.message || '加载实验详情失败')
  } finally {
    action.value = ''
  }
}

defineExpose({
  loading: computed(() => agentLoading.value || loading.value),
  stats: computed(() => ({
    samples: samples.value.length,
    candidates: candidates.value.length,
    experiments: experiments.value.length
  }))
})

onMounted(loadAgents)
</script>

<template>
  <div class="quality-loop-panel">
    <div class="quality-toolbar">
      <div>
        <h2>Agent 质量闭环</h2>
        <p>把真实运行沉淀为 Replay 样本，用同一条 AgentRun 链路比较 Prompt、模型和 Skill 版本。</p>
      </div>
      <div class="quality-toolbar-actions">
        <a-select
          v-model:value="selectedAgent"
          class="quality-agent-select"
          :options="availableAgents.map((agent) => ({ value: agent.id, label: agent.name || agent.id }))"
          placeholder="选择智能体"
          @change="load"
        />
        <a-button :disabled="agentLoading" :loading="agentLoading || loading" @click="loadAgents" title="刷新智能体和质量数据"><RefreshCw :size="14" /></a-button>
      </div>
    </div>

    <div v-if="agentLoading" class="quality-loading-state"><a-spin /></div>
    <a-alert v-else-if="error" type="error" :message="error" show-icon />
    <a-empty v-else-if="!selectedAgentItem" description="暂无可管理的主智能体" />
    <template v-else>
      <div class="quality-grid">
        <section class="quality-section">
          <div class="section-heading"><h3>Replay 样本</h3><span>{{ samples.length }} 条</span></div>
          <a-textarea v-model:value="sampleForm.input_text" :rows="3" placeholder="输入一次真实失败或边界问题" />
          <a-textarea v-model:value="sampleForm.expected_output" :rows="2" placeholder="可选：期望答案或必须包含的事实" />
          <a-button type="primary" :disabled="!sampleForm.input_text.trim()" :loading="action === 'sample'" @click="createSample"><Plus :size="14" />加入样本</a-button>
          <div v-if="samples.length" class="sample-list">
            <div v-for="sample in samples.slice(0, 5)" :key="sample.id" class="sample-item">
              <span>{{ sample.input_text }}</span><small>{{ sample.expected_output ? '有期望答案' : '仅回放' }}</small>
            </div>
          </div>
        </section>

        <section class="quality-section">
          <div class="section-heading"><h3>候选版本</h3><span>{{ candidates.length }} 个</span></div>
          <a-textarea v-model:value="candidateForm.system_prompt" :rows="3" placeholder="候选系统提示词" />
          <a-input v-model:value="candidateForm.model_spec" placeholder="可选：候选模型标识" />
          <a-input v-model:value="candidateForm.skill_slugs" placeholder="可选：Skill slug，逗号分隔" />
          <a-input v-model:value="candidateForm.change_summary" placeholder="变更说明" />
          <a-button :disabled="!selectedAgent" :loading="action === 'candidate'" @click="createCandidate"><FlaskConical :size="14" />保存候选</a-button>
          <div v-if="candidates.length" class="candidate-list">
            <div v-for="candidate in candidates.slice(0, 6)" :key="candidate.id" class="candidate-item">
              <div><strong>v{{ candidate.version }}</strong><span class="status">{{ candidate.status }}</span></div>
              <small>{{ candidate.change_summary || '未填写变更说明' }}</small>
              <div class="candidate-actions">
                <a-button size="small" :loading="action === 'experiment'" @click="runReplay(candidate.id)"><Play :size="12" />回放</a-button>
                <a-button v-if="candidate.status === 'draft'" size="small" :loading="action === candidate.id" @click="updateCandidate(candidate, 'approveCandidate')"><Check :size="12" />批准</a-button>
                <a-button v-if="candidate.status === 'approved'" size="small" type="primary" :loading="action === candidate.id" @click="updateCandidate(candidate, 'publishCandidate')"><Rocket :size="12" />发布</a-button>
                <a-button v-if="candidate.status === 'published'" size="small" :loading="action === candidate.id" @click="updateCandidate(candidate, 'rollbackCandidate')"><RotateCcw :size="12" />回滚</a-button>
              </div>
            </div>
          </div>
        </section>
      </div>

      <section class="quality-section experiment-section">
        <div class="section-heading"><h3>最近一次实验</h3><a-button size="small" :disabled="!samples.length || action === 'experiment'" :loading="action === 'experiment'" @click="runReplay()"><Play :size="12" />只跑基线</a-button></div>
        <a-empty v-if="!experiment" description="还没有回放实验" />
        <div v-else class="experiment-summary"><span>状态：{{ experiment.status }}</span><span>基线：{{ experiment.baseline_score ?? '-' }}</span><span>候选：{{ experiment.candidate_score ?? '-' }}</span><span>差值：{{ experiment.summary?.delta ?? '-' }}</span></div>
        <div v-if="experiments.length" class="experiment-list">
          <div v-for="item in experiments.slice(0, 8)" :key="item.id" class="experiment-item">
            <span>{{ item.created_at || item.id }}</span>
            <span>{{ item.status }} / {{ item.summary?.delta ?? '-' }}</span>
            <a-button size="small" type="text" :loading="action === `details-${item.id}`" title="查看逐样本结果" @click="showExperiment(item)"><Eye :size="13" /></a-button>
          </div>
        </div>
        <div v-if="experiment.results?.length" class="result-table-wrap">
          <a-table :data-source="experiment.results" :pagination="false" size="small" row-key="id">
            <a-table-column key="sample_id" data-index="sample_id" title="样本" />
            <a-table-column key="variant" data-index="variant" title="版本" />
            <a-table-column key="score" data-index="score" title="评分" />
            <a-table-column key="judge_reason" data-index="judge_reason" title="判定" />
            <a-table-column key="run_id" data-index="run_id" title="Run" />
          </a-table>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped lang="less">
.quality-loop-panel { padding: 18px var(--page-padding) 36px; }
.quality-toolbar, .section-heading, .quality-toolbar-actions, .candidate-actions, .experiment-summary { display: flex; align-items: center; gap: 10px; }
.quality-toolbar { justify-content: space-between; margin-bottom: 18px; }
.quality-agent-select { width: 190px; }
:deep(.quality-agent-select .ant-select-selection-item) { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.quality-toolbar h2, .quality-toolbar p, h3 { margin: 0; }
.quality-toolbar p { margin-top: 5px; color: var(--gray-600); font-size: 12px; }
.quality-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.quality-loading-state { display: flex; align-items: center; justify-content: center; min-height: 220px; }
.quality-section { display: flex; flex-direction: column; gap: 10px; padding: 16px; border: 1px solid var(--gray-100); border-radius: 7px; background: var(--gray-0); }
.section-heading { justify-content: space-between; color: var(--gray-700); }
.section-heading span, .status, small { color: var(--gray-500); font-size: 12px; }
.sample-list, .candidate-list { display: flex; flex-direction: column; gap: 6px; margin-top: 2px; }
.sample-item, .candidate-item { padding: 9px; border: 1px solid var(--gray-100); border-radius: 5px; background: var(--gray-10); }
.sample-item { display: flex; justify-content: space-between; gap: 8px; }
.sample-item span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.candidate-item > div:first-child { justify-content: space-between; display: flex; }
.candidate-item small { display: block; margin: 5px 0 8px; }
.candidate-actions { justify-content: flex-end; flex-wrap: wrap; }
.experiment-section { margin-top: 12px; }
.experiment-summary { flex-wrap: wrap; color: var(--gray-700); }
.experiment-list { display: flex; flex-direction: column; gap: 4px; }
.experiment-item { display: grid; grid-template-columns: minmax(0, 1fr) auto 28px; align-items: center; gap: 8px; padding: 6px 8px; border-top: 1px solid var(--gray-100); color: var(--gray-600); font-size: 12px; }
.experiment-item span:first-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.result-table-wrap { overflow-x: auto; }
@media (max-width: 760px) {
  .quality-toolbar, .quality-grid { grid-template-columns: 1fr; display: grid; }
  .quality-toolbar-actions { flex-wrap: wrap; }
  .quality-agent-select { width: min(190px, 100%); }
}
</style>
