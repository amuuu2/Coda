<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Clock3, Pause, Play, Plus, RefreshCw, Save, Trash2 } from 'lucide-vue-next'
import { message } from 'ant-design-vue'

import { agentApi } from '@/apis/agent_api'
import { automationApi } from '@/apis/automation_api'

const schedules = ref([])
const agents = ref([])
const runs = ref([])
const selectedId = ref(null)
const loading = ref(true)
const error = ref('')
const saving = ref(false)
const actionId = ref('')

const emptyForm = () => ({
  name: '',
  description: '',
  cron_expression: '0 9 * * 1',
  timezone: 'Asia/Shanghai',
  agent_slug: '',
  prompt: '生成经营周报，汇总关键指标、异常和行动建议。',
  knowledge_base_ids: [],
  skill_slugs: [],
  mcp_server_slugs: [],
  model_spec: null,
  output_config: { format: 'markdown' },
  enabled: true,
  max_retries: 2,
  retry_backoff_seconds: 60
})

const form = reactive(emptyForm())
const editingId = ref(null)

const selectedSchedule = computed(() => schedules.value.find((item) => item.id === selectedId.value) || null)
const enabledCount = computed(() => schedules.value.filter((item) => item.status === 'enabled').length)
const activeRunCount = computed(() => runs.value.filter((item) => ['pending', 'running'].includes(item.status)).length)

const resetForm = () => {
  Object.assign(form, emptyForm())
  if (agents.value[0]) form.agent_slug = agents.value[0].slug
  editingId.value = null
}

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const [scheduleResponse, agentResponse] = await Promise.all([automationApi.listSchedules(), agentApi.getAgents()])
    schedules.value = scheduleResponse.schedules || []
    agents.value = agentResponse.agents || []
    if (!selectedId.value && schedules.value[0]) selectSchedule(schedules.value[0])
    if (!form.agent_slug && agents.value[0]) form.agent_slug = agents.value[0].slug
  } catch (requestError) {
    error.value = requestError.message || '自动化任务加载失败'
  } finally {
    loading.value = false
  }
}

const selectSchedule = async (schedule) => {
  selectedId.value = schedule.id
  editingId.value = schedule.id
  Object.assign(form, {
    ...schedule,
    knowledge_base_ids: schedule.knowledge_base_ids || [],
    skill_slugs: schedule.skill_slugs || [],
    mcp_server_slugs: schedule.mcp_server_slugs || [],
    output_config: schedule.output_config || { format: 'markdown' }
  })
  try {
    const response = await automationApi.listRuns(schedule.id)
    runs.value = response.runs || []
  } catch (requestError) {
    message.error(requestError.message || '运行历史加载失败')
  }
}

const save = async () => {
  saving.value = true
  try {
    const payload = {
      ...form,
      knowledge_base_ids: form.knowledge_base_ids.filter(Boolean),
      skill_slugs: form.skill_slugs.filter(Boolean),
      mcp_server_slugs: form.mcp_server_slugs.filter(Boolean)
    }
    const response = editingId.value
      ? await automationApi.updateSchedule(editingId.value, payload)
      : await automationApi.createSchedule(payload)
    const schedule = response.schedule
    const index = schedules.value.findIndex((item) => item.id === schedule.id)
    if (index >= 0) schedules.value[index] = schedule
    else schedules.value.unshift(schedule)
    selectedId.value = schedule.id
    editingId.value = schedule.id
    Object.assign(form, schedule)
    message.success('任务已保存')
  } catch (requestError) {
    message.error(requestError.message || '任务保存失败')
  } finally {
    saving.value = false
  }
}

const runNow = async (schedule) => {
  actionId.value = schedule.id
  try {
    await automationApi.runSchedule(schedule.id)
    message.success('已提交立即运行')
    await load()
    if (selectedSchedule.value) await selectSchedule(selectedSchedule.value)
  } catch (requestError) {
    message.error(requestError.message || '立即运行失败')
  } finally {
    actionId.value = ''
  }
}

const toggle = async (schedule) => {
  actionId.value = schedule.id
  try {
    const response = schedule.status === 'enabled'
      ? await automationApi.disableSchedule(schedule.id)
      : await automationApi.enableSchedule(schedule.id)
    const index = schedules.value.findIndex((item) => item.id === schedule.id)
    if (index >= 0) schedules.value[index] = response.schedule
    if (selectedId.value === schedule.id) Object.assign(form, response.schedule)
  } catch (requestError) {
    message.error(requestError.message || '任务状态更新失败')
  } finally {
    actionId.value = ''
  }
}

const remove = async (schedule) => {
  actionId.value = schedule.id
  try {
    await automationApi.deleteSchedule(schedule.id)
    schedules.value = schedules.value.filter((item) => item.id !== schedule.id)
    if (selectedId.value === schedule.id) {
      selectedId.value = null
      runs.value = []
      resetForm()
    }
    message.success('任务已停用')
  } catch (requestError) {
    message.error(requestError.message || '任务停用失败')
  } finally {
    actionId.value = ''
  }
}

const statusClass = (status) => `enterprise-status enterprise-status--${status}`
const toLines = (value) => (value || []).join(', ')
const fromLines = (event) => event.target.value.split(',').map((item) => item.trim()).filter(Boolean)

onMounted(load)
</script>

<template>
  <main class="enterprise-page automation-center">
    <header class="enterprise-page__head">
      <div>
        <p class="enterprise-page__eyebrow">Enterprise reporting / automation</p>
        <h1>自动化中心</h1>
        <p class="enterprise-page__subhead">把文档、指标和 Agent 交付编排成可追溯的定时报告。</p>
      </div>
      <div class="enterprise-page__actions">
        <button type="button" class="enterprise-button" :disabled="loading" @click="load">
          <RefreshCw :size="15" /> 刷新
        </button>
        <button type="button" class="enterprise-button enterprise-button--primary" :disabled="saving" @click="resetForm">
          <Plus :size="15" /> 新建任务
        </button>
      </div>
    </header>

    <div class="enterprise-metrics">
      <div class="enterprise-metric"><span class="enterprise-metric__label">全部任务</span><strong class="enterprise-metric__value">{{ schedules.length }}</strong></div>
      <div class="enterprise-metric"><span class="enterprise-metric__label">运行中</span><strong class="enterprise-metric__value">{{ activeRunCount }}</strong></div>
      <div class="enterprise-metric"><span class="enterprise-metric__label">已启用</span><strong class="enterprise-metric__value">{{ enabledCount }}</strong></div>
      <div class="enterprise-metric"><span class="enterprise-metric__label">下次巡检</span><strong class="enterprise-metric__value">每分钟</strong></div>
    </div>

    <div v-if="loading" class="enterprise-loading">正在加载自动化任务...</div>
    <div v-else-if="error" class="enterprise-error">
      {{ error }}
      <button type="button" class="enterprise-button" @click="load">重试</button>
    </div>
    <div v-else class="enterprise-workspace">
      <section class="enterprise-section">
        <div class="enterprise-section__head"><h2>任务列表</h2><span class="enterprise-status">{{ schedules.length }} 项</span></div>
        <div v-if="!schedules.length" class="enterprise-empty">还没有定时任务，先创建一条经营报告任务。</div>
        <div v-else class="enterprise-list">
          <div
            v-for="schedule in schedules"
            :key="schedule.id"
            class="enterprise-list__item"
            :class="{ 'is-selected': selectedId === schedule.id }"
            @click="selectSchedule(schedule)"
          >
            <div>
              <div class="enterprise-list__title">{{ schedule.name }}</div>
              <div class="enterprise-list__meta">{{ schedule.cron_expression }} · {{ schedule.timezone }} · {{ schedule.agent_slug }}</div>
            </div>
            <div class="enterprise-inline-actions">
              <span :class="statusClass(schedule.status)">{{ schedule.status === 'enabled' ? '已启用' : '已暂停' }}</span>
              <button type="button" class="enterprise-button enterprise-button--quiet" :disabled="actionId === schedule.id" aria-label="立即运行" @click.stop="runNow(schedule)"><Play :size="14" /></button>
              <button type="button" class="enterprise-button enterprise-button--quiet" :disabled="actionId === schedule.id" aria-label="启停任务" @click.stop="toggle(schedule)"><Pause :size="14" /></button>
            </div>
          </div>
        </div>
      </section>

      <section class="enterprise-section">
        <div class="enterprise-section__head">
          <h2>{{ editingId ? '编辑任务' : '新建任务' }}</h2>
          <button v-if="editingId" type="button" class="enterprise-button enterprise-button--quiet" @click="resetForm"><Plus :size="14" /> 新建</button>
        </div>
        <div class="enterprise-section__body">
          <form class="enterprise-form" @submit.prevent="save">
            <div class="enterprise-form__grid">
              <div class="enterprise-field"><label for="schedule-name">任务名称</label><input id="schedule-name" v-model="form.name" required /></div>
              <div class="enterprise-field"><label for="schedule-agent">Agent</label><select id="schedule-agent" v-model="form.agent_slug" required><option value="" disabled>选择 Agent</option><option v-for="agent in agents" :key="agent.slug" :value="agent.slug">{{ agent.name }} · {{ agent.slug }}</option></select></div>
              <div class="enterprise-field"><label for="schedule-cron">Cron</label><input id="schedule-cron" v-model="form.cron_expression" required /></div>
              <div class="enterprise-field"><label for="schedule-timezone">时区</label><input id="schedule-timezone" v-model="form.timezone" required /></div>
              <div class="enterprise-field"><label for="schedule-format">输出格式</label><select id="schedule-format" v-model="form.output_config.format"><option value="markdown">Markdown</option><option value="html">HTML</option><option value="pdf">PDF</option></select></div>
              <div class="enterprise-field"><label for="schedule-retries">失败重试次数</label><input id="schedule-retries" v-model.number="form.max_retries" type="number" min="0" max="3" /></div>
              <div class="enterprise-field enterprise-field--wide"><label for="schedule-prompt">提示词</label><textarea id="schedule-prompt" v-model="form.prompt" required /></div>
              <div class="enterprise-field enterprise-field--wide"><label for="schedule-kbs">知识库 ID（逗号分隔）</label><input id="schedule-kbs" :value="toLines(form.knowledge_base_ids)" @input="form.knowledge_base_ids = fromLines($event)" /></div>
              <div class="enterprise-field enterprise-field--wide"><label for="schedule-skills">Skills（逗号分隔）</label><input id="schedule-skills" :value="toLines(form.skill_slugs)" @input="form.skill_slugs = fromLines($event)" /></div>
              <div class="enterprise-field enterprise-field--wide"><label for="schedule-mcp">MCP 服务（逗号分隔）</label><input id="schedule-mcp" :value="toLines(form.mcp_server_slugs)" @input="form.mcp_server_slugs = fromLines($event)" /></div>
            </div>
            <div class="enterprise-inline-actions">
              <button type="submit" class="enterprise-button enterprise-button--primary" :disabled="saving || !form.agent_slug"><Save :size="15" /> {{ saving ? '保存中' : '保存任务' }}</button>
              <span v-if="selectedSchedule" class="enterprise-status"><Clock3 :size="14" /> 下次：{{ selectedSchedule.next_run_at || '等待计算' }}</span>
            </div>
          </form>

          <div v-if="selectedSchedule" class="automation-history">
            <div class="enterprise-section__head"><h2>运行历史</h2><span class="enterprise-status">{{ runs.length }} 条</span></div>
            <div v-if="!runs.length" class="enterprise-empty">还没有运行记录。</div>
            <div v-else class="enterprise-table-wrap">
              <table class="enterprise-table"><thead><tr><th>计划时间</th><th>状态</th><th>耗时</th><th>错误</th></tr></thead><tbody><tr v-for="run in runs" :key="run.id"><td>{{ run.planned_at }}</td><td><span :class="statusClass(run.status)">{{ run.status }}</span></td><td>{{ run.duration_ms ? `${run.duration_ms} ms` : '-' }}</td><td>{{ run.error_message || '-' }}</td></tr></tbody></table>
            </div>
            <button type="button" class="enterprise-button enterprise-button--quiet automation-delete" :disabled="actionId === selectedSchedule.id" @click="remove(selectedSchedule)"><Trash2 :size="14" /> 停用任务</button>
          </div>
        </div>
      </section>
    </div>
  </main>
</template>

<style lang="less">
@import '@/assets/css/enterprise.less';

.automation-history {
  margin-top: 28px;
  border-top: 1px solid var(--gray-150);
}

.automation-history .enterprise-section__head {
  padding: 0;
  border-bottom: 0;
}

.automation-delete {
  margin-top: 10px;
  color: var(--color-error-700);
}
</style>
