<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Database, Play, Plus, RefreshCw, Save, ShieldCheck, Table2, Trash2, Wifi, X } from 'lucide-vue-next'
import { message } from 'ant-design-vue'

import { analyticsApi } from '@/apis/analytics_api'

const sources = ref([])
const schemaTables = ref([])
const queries = ref([])
const selectedSourceId = ref(null)
const selectedQuery = ref(null)
const loading = ref(true)
const error = ref('')
const saving = ref(false)
const actionId = ref('')
const showSourceForm = ref(false)

const emptySource = () => ({
  name: '',
  db_type: 'postgresql',
  host: '',
  port: 5432,
  database_name: '',
  username: '',
  password: '',
  password_env: '',
  table_allowlist: ''
})

const sourceForm = reactive(emptySource())
const queryForm = reactive({ data_source_id: '', question: '', sql: '', model_spec: '', timeout_seconds: 30, max_rows: 1000 })

const selectedSource = computed(() => sources.value.find((source) => source.id === selectedSourceId.value) || null)
const successCount = computed(() => queries.value.filter((query) => query.status === 'success').length)
const chartPoints = computed(() => {
  const result = selectedQuery.value
  const chart = result?.chart
  if (!chart || !result.rows?.length) return []
  return result.rows.slice(0, 10).map((row) => ({ label: row[chart.dimension], value: Number(row[chart.metrics[0]]) || 0 }))
})
const maxChartValue = computed(() => Math.max(...chartPoints.value.map((point) => point.value), 1))

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const [sourceResponse, queryResponse] = await Promise.all([analyticsApi.listDataSources(), analyticsApi.listQueries()])
    sources.value = sourceResponse.data_sources || []
    queries.value = queryResponse.queries || []
    if (selectedSourceId.value) {
      const source = sources.value.find((item) => item.id === selectedSourceId.value)
      if (source) await selectSource(source, false)
      else {
        selectedSourceId.value = null
        queryForm.data_source_id = ''
        schemaTables.value = []
        showSourceForm.value = false
      }
    }
  } catch (requestError) {
    error.value = requestError.message || '数据分析工作台加载失败'
  } finally {
    loading.value = false
  }
}

const selectSource = async (source, openForm = true) => {
  selectedSourceId.value = source.id
  queryForm.data_source_id = source.id
  if (openForm) showSourceForm.value = true
  Object.assign(sourceForm, { ...emptySource(), ...source, table_allowlist: (source.table_allowlist || []).join(', ') })
  try {
    const response = await analyticsApi.listSchema(source.id)
    schemaTables.value = response.tables || []
  } catch (requestError) {
    message.error(requestError.message || 'Schema 加载失败')
  }
}

const saveSource = async () => {
  saving.value = true
  try {
    const payload = {
      ...sourceForm,
      table_allowlist: sourceForm.table_allowlist.split(',').map((item) => item.trim()).filter(Boolean),
      port: Number(sourceForm.port)
    }
    const response = selectedSourceId.value
      ? await analyticsApi.updateDataSource(selectedSourceId.value, payload)
      : await analyticsApi.createDataSource(payload)
    const source = response.data_source
    const index = sources.value.findIndex((item) => item.id === source.id)
    if (index >= 0) sources.value[index] = source
    else sources.value.unshift(source)
    await selectSource(source)
    message.success('数据源已保存')
  } catch (requestError) {
    message.error(requestError.message || '数据源保存失败')
  } finally {
    saving.value = false
  }
}

const openNewSource = () => {
  selectedSourceId.value = null
  schemaTables.value = []
  selectedQuery.value = null
  queryForm.data_source_id = ''
  Object.assign(sourceForm, emptySource())
  showSourceForm.value = true
}

const closeSourceForm = () => {
  showSourceForm.value = false
}

const testSource = async (source) => {
  actionId.value = source.id
  try {
    await analyticsApi.testDataSource(source.id)
    message.success('连接测试成功')
    await load()
  } catch (requestError) {
    message.error(requestError.message || '连接测试失败')
  } finally {
    actionId.value = ''
  }
}

const syncSchema = async (source) => {
  actionId.value = source.id
  try {
    const response = await analyticsApi.syncSchema(source.id)
    schemaTables.value = response.tables || []
    message.success('Schema 已同步')
  } catch (requestError) {
    message.error(requestError.message || 'Schema 同步失败')
  } finally {
    actionId.value = ''
  }
}

const removeSource = async (source) => {
  actionId.value = source.id
  try {
    await analyticsApi.deleteDataSource(source.id)
    sources.value = sources.value.filter((item) => item.id !== source.id)
    if (selectedSourceId.value === source.id) {
      selectedSourceId.value = null
      schemaTables.value = []
      selectedQuery.value = null
      queryForm.data_source_id = ''
      showSourceForm.value = false
    }
    message.success('数据源已删除')
  } catch (requestError) {
    message.error(requestError.message || '数据源删除失败')
  } finally {
    actionId.value = ''
  }
}

const runQuery = async () => {
  if (!queryForm.data_source_id || !queryForm.question.trim()) return
  saving.value = true
  selectedQuery.value = null
  try {
    const response = await analyticsApi.runQuery({ ...queryForm, sql: queryForm.sql || null })
    selectedQuery.value = response.query
    queries.value = [response.query, ...queries.value.filter((query) => query.id !== response.query.id)]
    message.success('查询已完成')
  } catch (requestError) {
    message.error(requestError.message || '查询失败')
  } finally {
    saving.value = false
  }
}

const openQuery = async (query) => {
  try {
    const response = await analyticsApi.getQuery(query.id)
    selectedQuery.value = response.query
  } catch (requestError) {
    message.error(requestError.message || '查询详情加载失败')
  }
}

const statusClass = (status) => `enterprise-status enterprise-status--${status}`

onMounted(load)
</script>

<template>
  <main class="enterprise-page analytics-workbench">
    <header class="enterprise-page__head">
      <div>
        <p class="enterprise-page__eyebrow">Enterprise reporting / analytics</p>
        <h1>数据分析工作台</h1>
        <p class="enterprise-page__subhead">从白名单 Schema 到可审计 SQL，每次提问都留下可复核的证据链。</p>
      </div>
      <div class="enterprise-page__actions"><button type="button" class="enterprise-button" :disabled="loading" @click="load"><RefreshCw :size="15" /> 刷新</button><button type="button" class="enterprise-button enterprise-button--primary" @click="openNewSource"><Plus :size="15" /> 新建数据源</button></div>
    </header>

    <div class="enterprise-metrics"><div class="enterprise-metric"><span class="enterprise-metric__label">数据源</span><strong class="enterprise-metric__value">{{ sources.length }}</strong></div><div class="enterprise-metric"><span class="enterprise-metric__label">已同步表</span><strong class="enterprise-metric__value">{{ schemaTables.length }}</strong></div><div class="enterprise-metric"><span class="enterprise-metric__label">查询总数</span><strong class="enterprise-metric__value">{{ queries.length }}</strong></div><div class="enterprise-metric"><span class="enterprise-metric__label">成功查询</span><strong class="enterprise-metric__value">{{ successCount }}</strong></div></div>

    <div v-if="loading" class="enterprise-loading">正在加载数据源和查询历史...</div>
    <div v-else-if="error" class="enterprise-error">{{ error }}<button type="button" class="enterprise-button" @click="load">重试</button></div>
    <div v-else class="enterprise-workspace">
      <section class="enterprise-section">
        <div class="enterprise-section__head"><h2>数据源</h2><div class="enterprise-inline-actions"><span class="enterprise-status">{{ sources.length }} 项</span><button v-if="showSourceForm" type="button" class="enterprise-button enterprise-button--quiet" aria-label="收起数据源表单" @click="closeSourceForm"><X :size="14" /> 收起</button></div></div>
        <div v-if="showSourceForm" class="enterprise-section__body">
          <form class="enterprise-form" @submit.prevent="saveSource">
            <div class="enterprise-form__grid"><div class="enterprise-field"><label for="source-name">名称</label><input id="source-name" v-model="sourceForm.name" required /></div><div class="enterprise-field"><label for="source-type">类型</label><select id="source-type" v-model="sourceForm.db_type"><option value="postgresql">PostgreSQL</option><option value="mysql">MySQL</option></select></div><div class="enterprise-field"><label for="source-host">主机</label><input id="source-host" v-model="sourceForm.host" required /></div><div class="enterprise-field"><label for="source-port">端口</label><input id="source-port" v-model.number="sourceForm.port" type="number" min="1" max="65535" /></div><div class="enterprise-field"><label for="source-database">数据库</label><input id="source-database" v-model="sourceForm.database_name" required /></div><div class="enterprise-field"><label for="source-username">用户名</label><input id="source-username" v-model="sourceForm.username" required /></div><div class="enterprise-field"><label for="source-password">密码</label><input id="source-password" v-model="sourceForm.password" type="password" autocomplete="new-password" placeholder="仅在变更时填写" /></div><div class="enterprise-field"><label for="source-password-env">密码环境变量</label><input id="source-password-env" v-model="sourceForm.password_env" placeholder="可选" /></div><div class="enterprise-field enterprise-field--wide"><label for="source-allowlist">表白名单</label><input id="source-allowlist" v-model="sourceForm.table_allowlist" placeholder="public.orders, public.sales" /></div></div>
            <div class="enterprise-inline-actions"><button type="submit" class="enterprise-button enterprise-button--primary" :disabled="saving"><Save :size="14" /> {{ saving ? '保存中' : '保存数据源' }}</button><button type="button" class="enterprise-button" @click="openNewSource">清空</button></div>
          </form>
        </div>
        <div v-if="!sources.length" class="enterprise-empty">还没有数据源。</div>
        <div v-else class="enterprise-list">
          <div v-for="source in sources" :key="source.id" class="enterprise-list__item" :class="{ 'is-selected': selectedSourceId === source.id }" @click="selectSource(source)"><div><div class="enterprise-list__title"><Database :size="14" /> {{ source.name }}</div><div class="enterprise-list__meta">{{ source.db_type }} · {{ source.host }}:{{ source.port }}/{{ source.database_name }}</div></div><div class="enterprise-inline-actions"><button type="button" class="enterprise-button enterprise-button--quiet" :disabled="actionId === source.id" aria-label="测试连接" @click.stop="testSource(source)"><Wifi :size="14" /></button><button type="button" class="enterprise-button enterprise-button--quiet" :disabled="actionId === source.id" aria-label="同步 Schema" @click.stop="syncSchema(source)"><RefreshCw :size="14" /></button><button type="button" class="enterprise-button enterprise-button--quiet" :disabled="actionId === source.id" aria-label="删除数据源" @click.stop="removeSource(source)"><Trash2 :size="14" /></button></div></div>
        </div>
      </section>

      <section class="enterprise-section">
        <div class="enterprise-section__head"><h2>提问与结果</h2><span v-if="selectedSource" class="enterprise-status enterprise-status--enabled"><ShieldCheck :size="14" /> {{ selectedSource.name }}</span></div>
        <div v-if="!selectedSource" class="enterprise-empty analytics-empty-state">选择一个数据源后开始提问。</div>
        <template v-else>
          <div class="enterprise-section__body">
          <form class="enterprise-form" @submit.prevent="runQuery"><div class="enterprise-field"><label for="query-question">自然语言问题</label><textarea id="query-question" v-model="queryForm.question" placeholder="最近一周各区域收入和订单数是多少？" required /></div><div class="enterprise-field"><label for="query-sql">SQL（可选，提交前仍会通过 AST 和白名单校验）</label><textarea id="query-sql" v-model="queryForm.sql" class="enterprise-code" placeholder="留空由分析模型生成 SQL" /></div><div class="enterprise-inline-actions"><button type="submit" class="enterprise-button enterprise-button--primary" :disabled="saving || !queryForm.data_source_id || !queryForm.question.trim()"><Play :size="14" /> {{ saving ? '查询中' : '运行查询' }}</button></div></form>
          <div v-if="selectedQuery" class="analytics-result"><div class="enterprise-detail-grid"><div class="enterprise-detail-cell"><span class="enterprise-detail-cell__label">状态</span><strong class="enterprise-detail-cell__value"><span :class="statusClass(selectedQuery.status)">{{ selectedQuery.status }}</span></strong></div><div class="enterprise-detail-cell"><span class="enterprise-detail-cell__label">行数</span><strong class="enterprise-detail-cell__value">{{ selectedQuery.row_count }}</strong></div><div class="enterprise-detail-cell"><span class="enterprise-detail-cell__label">耗时</span><strong class="enterprise-detail-cell__value">{{ selectedQuery.duration_ms }} ms</strong></div><div class="enterprise-detail-cell"><span class="enterprise-detail-cell__label">结论</span><strong class="enterprise-detail-cell__value">{{ selectedQuery.conclusion || selectedQuery.error_message }}</strong></div></div><pre class="enterprise-code">{{ selectedQuery.sql_text }}</pre><div v-if="chartPoints.length" class="analytics-chart"><div v-for="point in chartPoints" :key="point.label" class="analytics-chart__item"><span class="analytics-chart__label">{{ point.label }}</span><span class="analytics-chart__bar" :style="{ width: `${Math.max(4, point.value / maxChartValue * 100)}%` }" /><strong>{{ point.value }}</strong></div></div><div class="enterprise-table-wrap"><table class="enterprise-table"><thead><tr><th v-for="column in selectedQuery.columns" :key="column">{{ column }}</th></tr></thead><tbody><tr v-for="(row, rowIndex) in selectedQuery.rows" :key="rowIndex"><td v-for="column in selectedQuery.columns" :key="column">{{ row[column] }}</td></tr></tbody></table></div></div><div v-else class="enterprise-empty">提交问题后，SQL、表格、图表和结论会在这里出现。</div>
          </div>
          <div class="analytics-schema"><div class="enterprise-section__head"><h2><Table2 :size="15" /> Schema 白名单</h2><span class="enterprise-status">{{ schemaTables.length }} 张表</span></div><div v-if="!schemaTables.length" class="enterprise-empty">尚未同步 Schema。</div><div v-else class="enterprise-table-wrap"><table class="enterprise-table"><thead><tr><th>表</th><th>列</th><th>状态</th></tr></thead><tbody><tr v-for="table in schemaTables" :key="table.id"><td>{{ table.schema_name }}.{{ table.table_name }}</td><td>{{ table.columns?.map((column) => column.name).join(', ') }}</td><td><span :class="statusClass(table.is_allowed ? 'enabled' : 'disabled')">{{ table.is_allowed ? '允许' : '拒绝' }}</span></td></tr></tbody></table></div></div>
        </template>
      </section>
    </div>

    <section class="enterprise-section analytics-history"><div class="enterprise-section__head"><h2>查询历史</h2><span class="enterprise-status">{{ queries.length }} 条</span></div><div v-if="!queries.length" class="enterprise-empty">暂无查询审计记录。</div><div v-else class="enterprise-list"><button v-for="query in queries" :key="query.id" type="button" class="enterprise-list__item" @click="openQuery(query)"><div><div class="enterprise-list__title">{{ query.question }}</div><div class="enterprise-list__meta">{{ query.created_at }} · {{ query.row_count ?? 0 }} 行</div></div><span :class="statusClass(query.status)">{{ query.status }}</span></button></div></section>
  </main>
</template>

<style lang="less">
@import '@/assets/css/enterprise.less';

.analytics-workbench .enterprise-list__title {
  display: flex;
  align-items: center;
  gap: 7px;
}

.analytics-empty-state {
  display: flex;
  min-height: 220px;
  align-items: center;
  justify-content: center;
  padding: 18px;
  text-align: center;
}

.analytics-result {
  display: grid;
  gap: 14px;
  margin-top: 24px;
}

.analytics-chart {
  display: grid;
  gap: 8px;
  padding: 14px;
  border-left: 3px solid var(--main-500);
  background: var(--main-30);
}

.analytics-chart__item {
  display: grid;
  grid-template-columns: minmax(80px, 0.35fr) minmax(100px, 1fr) auto;
  align-items: center;
  gap: 10px;
  color: var(--gray-700);
  font-size: 12px;
}

.analytics-chart__label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.analytics-chart__bar {
  display: block;
  height: 8px;
  border-radius: 4px;
  background: var(--main-500);
}

.analytics-schema {
  margin-top: 28px;
  border-top: 1px solid var(--gray-150);
}

.analytics-schema .enterprise-section__head {
  padding: 0;
  border-bottom: 0;
}

.analytics-history {
  max-width: 1420px;
  margin: 18px auto 0;
}
</style>
