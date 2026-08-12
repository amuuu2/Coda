<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Download, FileCheck2, Plus, RefreshCw, Save, ScanText } from 'lucide-vue-next'
import { message } from 'ant-design-vue'

import { extractionApi } from '@/apis/extraction_api'
import { databaseApi } from '@/apis/knowledge_api'

const activeTab = ref('batches')
const templates = ref([])
const batches = ref([])
const knowledgeBases = ref([])
const selectedBatch = ref(null)
const tasks = ref([])
const selectedTask = ref(null)
const revisions = ref([])
const loading = ref(true)
const error = ref('')
const saving = ref(false)
const actionId = ref('')

const newTemplate = () => ({
  name: '',
  schema_json: JSON.stringify({ type: 'object', properties: { metric: { type: 'number' } }, required: ['metric'] }, null, 2),
  field_descriptions: '{}',
  required_fields: '',
  prompt: '抽取经营指标和原文证据。',
  version: 1,
  is_active: true
})

const newBatch = () => ({ template_id: templates.value[0]?.id || '', file_ids: '', kb_id: '', files: [] })
const templateForm = reactive(newTemplate())
const batchForm = reactive(newBatch())
const revisionForm = reactive({ result_json: '{}', evidence: '[]' })
const editingTemplateId = ref(null)

const successCount = computed(() => batches.value.reduce((sum, batch) => sum + (batch.succeeded_count || 0), 0))
const totalTaskCount = computed(() => batches.value.reduce((sum, batch) => sum + (batch.total_count || 0), 0))
const batchInputReady = computed(() => Boolean(batchForm.file_ids.trim() || batchForm.files.length))

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const [templateResponse, batchResponse, knowledgeBaseResponse] = await Promise.all([
      extractionApi.listTemplates(),
      extractionApi.listBatches(),
      databaseApi.getAccessibleDatabases()
    ])
    templates.value = templateResponse.templates || []
    batches.value = batchResponse.batches || []
    knowledgeBases.value = (knowledgeBaseResponse.databases || []).filter((item) => item.supports_documents)
    if (!batchForm.template_id && templates.value[0]) batchForm.template_id = templates.value[0].id
    if (!batchForm.kb_id && knowledgeBases.value[0]) batchForm.kb_id = knowledgeBases.value[0].kb_id
  } catch (requestError) {
    error.value = requestError.message || '抽取中心加载失败'
  } finally {
    loading.value = false
  }
}

const editTemplate = (template) => {
  editingTemplateId.value = template.id
  Object.assign(templateForm, {
    ...template,
    schema_json: JSON.stringify(template.schema_json || {}, null, 2),
    field_descriptions: JSON.stringify(template.field_descriptions || {}, null, 2),
    required_fields: (template.required_fields || []).join(', ')
  })
  activeTab.value = 'templates'
}

const resetTemplate = () => {
  editingTemplateId.value = null
  Object.assign(templateForm, newTemplate())
}

const saveTemplate = async () => {
  saving.value = true
  try {
    const payload = {
      ...templateForm,
      schema_json: JSON.parse(templateForm.schema_json),
      field_descriptions: JSON.parse(templateForm.field_descriptions || '{}'),
      required_fields: templateForm.required_fields.split(',').map((item) => item.trim()).filter(Boolean)
    }
    const response = editingTemplateId.value
      ? await extractionApi.updateTemplate(editingTemplateId.value, payload)
      : await extractionApi.createTemplate(payload)
    const template = response.template
    const index = templates.value.findIndex((item) => item.id === template.id)
    if (index >= 0) templates.value[index] = template
    else templates.value.unshift(template)
    editTemplate(template)
    message.success('模板已保存')
  } catch (requestError) {
    message.error(requestError.message || '模板保存失败，请检查 JSON')
  } finally {
    saving.value = false
  }
}

const createBatch = async () => {
  saving.value = true
  try {
    const response = batchForm.files.length
      ? await extractionApi.createUploadBatch({
          templateId: batchForm.template_id,
          kbId: batchForm.kb_id,
          files: batchForm.files
        })
      : await extractionApi.createBatch({
          template_id: batchForm.template_id,
          file_ids: batchForm.file_ids.split(/[\n,]/).map((item) => item.trim()).filter(Boolean)
        })
    batches.value.unshift(response.batch)
    await selectBatch(response.batch)
    message.success('抽取批次已排队')
  } catch (requestError) {
    message.error(requestError.message || '批次创建失败')
  } finally {
    saving.value = false
  }
}

const selectBatch = async (batch) => {
  actionId.value = batch.id
  try {
    const response = await extractionApi.getBatch(batch.id)
    selectedBatch.value = response.batch
    tasks.value = response.tasks || []
    selectedTask.value = tasks.value[0] || null
    if (selectedTask.value) await selectTask(selectedTask.value)
  } catch (requestError) {
    message.error(requestError.message || '批次详情加载失败')
  } finally {
    actionId.value = ''
  }
}

const selectTask = async (task) => {
  try {
    const response = await extractionApi.getTask(task.id)
    selectedTask.value = response.task
    const taskIndex = tasks.value.findIndex((item) => item.id === response.task.id)
    if (taskIndex >= 0) tasks.value[taskIndex] = response.task
    revisions.value = response.revisions || []
    revisionForm.result_json = JSON.stringify(response.task.extracted_result || {}, null, 2)
    revisionForm.evidence = JSON.stringify(response.task.evidence || [], null, 2)
  } catch (requestError) {
    message.error(requestError.message || '抽取结果加载失败')
  }
}

const rerun = async (batch) => {
  actionId.value = batch.id
  try {
    await extractionApi.rerunBatch(batch.id)
    message.success('批次已重新排队')
    await load()
    const refreshed = batches.value.find((item) => item.id === batch.id)
    if (refreshed) await selectBatch(refreshed)
  } catch (requestError) {
    message.error(requestError.message || '批次重跑失败')
  } finally {
    actionId.value = ''
  }
}

const cancel = async (batch) => {
  actionId.value = batch.id
  try {
    await extractionApi.cancelBatch(batch.id)
    message.success('批次已取消')
    await load()
    const refreshed = batches.value.find((item) => item.id === batch.id)
    if (refreshed) await selectBatch(refreshed)
  } catch (requestError) {
    message.error(requestError.message || '批次取消失败')
  } finally {
    actionId.value = ''
  }
}

const revise = async () => {
  if (!selectedTask.value) return
  saving.value = true
  try {
    const response = await extractionApi.reviseTask(selectedTask.value.id, {
      result_json: JSON.parse(revisionForm.result_json),
      evidence: JSON.parse(revisionForm.evidence || '[]')
    })
    selectedTask.value = response.task
    revisions.value.unshift(response.revision)
    message.success('人工修订已保存')
  } catch (requestError) {
    message.error(requestError.message || '修订保存失败，请检查 JSON')
  } finally {
    saving.value = false
  }
}

const download = async (format) => {
  if (!selectedBatch.value) return
  try {
    const response = await extractionApi.exportBatch(selectedBatch.value.id, format)
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `extraction-${selectedBatch.value.id}.${format}`
    link.click()
    URL.revokeObjectURL(url)
  } catch (requestError) {
    message.error(requestError.message || '导出失败')
  }
}

const statusClass = (status) => `enterprise-status enterprise-status--${status}`

onMounted(load)
</script>

<template>
  <main class="enterprise-page extraction-center">
    <header class="enterprise-page__head">
      <div>
        <p class="enterprise-page__eyebrow">Enterprise reporting / extraction</p>
        <h1>抽取中心</h1>
        <p class="enterprise-page__subhead">让每个字段都带着模板版本、校验结果和可回看的原文证据。</p>
      </div>
      <div class="enterprise-page__actions">
        <button type="button" class="enterprise-button" :disabled="loading" @click="load"><RefreshCw :size="15" /> 刷新</button>
        <button type="button" class="enterprise-button enterprise-button--primary" @click="activeTab = 'templates'; resetTemplate()"><Plus :size="15" /> 新建模板</button>
      </div>
    </header>

    <div class="enterprise-metrics">
      <div class="enterprise-metric"><span class="enterprise-metric__label">模板版本</span><strong class="enterprise-metric__value">{{ templates.length }}</strong></div>
      <div class="enterprise-metric"><span class="enterprise-metric__label">批次</span><strong class="enterprise-metric__value">{{ batches.length }}</strong></div>
      <div class="enterprise-metric"><span class="enterprise-metric__label">文档任务</span><strong class="enterprise-metric__value">{{ totalTaskCount }}</strong></div>
      <div class="enterprise-metric"><span class="enterprise-metric__label">已完成字段</span><strong class="enterprise-metric__value">{{ successCount }}</strong></div>
    </div>

    <div v-if="loading" class="enterprise-loading">正在加载抽取数据...</div>
    <div v-else-if="error" class="enterprise-error">{{ error }}<button type="button" class="enterprise-button" @click="load">重试</button></div>
    <div v-else class="enterprise-workspace">
      <section class="enterprise-section">
        <div class="enterprise-section__head"><h2>抽取对象</h2><div class="enterprise-inline-actions"><button type="button" class="enterprise-button enterprise-button--quiet" :class="{ 'is-active': activeTab === 'batches' }" @click="activeTab = 'batches'"><ScanText :size="14" /> 批次</button><button type="button" class="enterprise-button enterprise-button--quiet" :class="{ 'is-active': activeTab === 'templates' }" @click="activeTab = 'templates'"><FileCheck2 :size="14" /> 模板</button></div></div>
        <div v-if="activeTab === 'batches'">
          <div class="enterprise-section__body extraction-create">
            <div class="enterprise-form__grid">
              <div class="enterprise-field"><label for="batch-template">模板</label><select id="batch-template" v-model="batchForm.template_id"><option value="" disabled>选择模板</option><option v-for="template in templates" :key="template.id" :value="template.id">{{ template.name }} · v{{ template.version }}</option></select></div>
              <div class="enterprise-field"><label for="batch-kb">上传到知识库</label><select id="batch-kb" v-model="batchForm.kb_id"><option value="" disabled>选择知识库</option><option v-for="knowledgeBase in knowledgeBases" :key="knowledgeBase.kb_id" :value="knowledgeBase.kb_id">{{ knowledgeBase.name }}</option></select></div>
              <div class="enterprise-field enterprise-field--wide"><label for="batch-files">已有知识文件 ID</label><textarea id="batch-files" v-model="batchForm.file_ids" placeholder="file_id，每行一个" /></div>
              <div class="enterprise-field enterprise-field--wide"><label for="batch-upload">批量上传文档</label><input id="batch-upload" type="file" multiple @change="batchForm.files = Array.from($event.target.files || [])" /></div>
            </div>
            <button type="button" class="enterprise-button enterprise-button--primary" :disabled="saving || !batchForm.template_id || !batchInputReady || (batchForm.files.length > 0 && !batchForm.kb_id)" @click="createBatch"><Plus :size="14" /> {{ saving ? '提交中' : '创建批次' }}</button>
          </div>
          <div v-if="!batches.length" class="enterprise-empty">还没有抽取批次。</div>
          <div v-else class="enterprise-list">
            <button v-for="batch in batches" :key="batch.id" type="button" class="enterprise-list__item" :class="{ 'is-selected': selectedBatch?.id === batch.id }" @click="selectBatch(batch)"><div><div class="enterprise-list__title">{{ batch.id }}</div><div class="enterprise-list__meta">{{ batch.succeeded_count }}/{{ batch.total_count }} 完成 · {{ batch.created_at }}</div></div><span :class="statusClass(batch.status)">{{ batch.status }}</span></button>
          </div>
        </div>
        <div v-else class="enterprise-section__body">
          <form class="enterprise-form" @submit.prevent="saveTemplate">
            <div class="enterprise-form__grid"><div class="enterprise-field"><label for="template-name">模板名称</label><input id="template-name" v-model="templateForm.name" required /></div><div class="enterprise-field"><label for="template-version">版本</label><input id="template-version" v-model.number="templateForm.version" type="number" min="1" /></div><div class="enterprise-field enterprise-field--wide"><label for="template-schema">JSON Schema</label><textarea id="template-schema" v-model="templateForm.schema_json" class="enterprise-tall-input" required /></div><div class="enterprise-field enterprise-field--wide"><label for="template-descriptions">字段说明 JSON</label><textarea id="template-descriptions" v-model="templateForm.field_descriptions" /></div><div class="enterprise-field"><label for="template-required">必填字段</label><input id="template-required" v-model="templateForm.required_fields" placeholder="字段名，逗号分隔" /></div><div class="enterprise-field"><label for="template-prompt">提示词</label><input id="template-prompt" v-model="templateForm.prompt" /></div></div>
            <div class="enterprise-inline-actions"><button type="submit" class="enterprise-button enterprise-button--primary" :disabled="saving"><Save :size="14" /> {{ saving ? '保存中' : '保存模板' }}</button><button type="button" class="enterprise-button" @click="resetTemplate">清空</button></div>
          </form>
          <div class="enterprise-list extraction-template-list"><button v-for="template in templates" :key="template.id" type="button" class="enterprise-list__item" :class="{ 'is-selected': editingTemplateId === template.id }" @click="editTemplate(template)"><div><div class="enterprise-list__title">{{ template.name }}</div><div class="enterprise-list__meta">v{{ template.version }} · {{ template.required_fields?.length || 0 }} 个必填字段</div></div><span :class="statusClass(template.is_active ? 'enabled' : 'disabled')">{{ template.is_active ? '启用' : '停用' }}</span></button></div>
        </div>
      </section>

      <section class="enterprise-section">
        <div class="enterprise-section__head"><h2>{{ selectedBatch ? '结果与证据' : '批次详情' }}</h2><div v-if="selectedBatch" class="enterprise-inline-actions"><button type="button" class="enterprise-button enterprise-button--quiet" @click="download('json')"><Download :size="14" /> JSON</button><button type="button" class="enterprise-button enterprise-button--quiet" @click="download('csv')"><Download :size="14" /> CSV</button></div></div>
        <div v-if="!selectedBatch" class="enterprise-empty">选择一个批次查看进度、结果和人工修订记录。</div>
        <div v-else class="enterprise-section__body">
          <div class="enterprise-detail-grid"><div class="enterprise-detail-cell"><span class="enterprise-detail-cell__label">批次状态</span><strong class="enterprise-detail-cell__value"><span :class="statusClass(selectedBatch.status)">{{ selectedBatch.status }}</span></strong></div><div class="enterprise-detail-cell"><span class="enterprise-detail-cell__label">模板版本</span><strong class="enterprise-detail-cell__value">v{{ selectedBatch.template_version }}</strong></div><div class="enterprise-detail-cell"><span class="enterprise-detail-cell__label">成功 / 失败</span><strong class="enterprise-detail-cell__value">{{ selectedBatch.succeeded_count }} / {{ selectedBatch.failed_count }}</strong></div><div class="enterprise-detail-cell"><span class="enterprise-detail-cell__label">模型</span><strong class="enterprise-detail-cell__value">{{ selectedBatch.model_spec || '系统默认' }}</strong></div></div>
          <div v-if="!selectedTask" class="enterprise-empty">该批次还没有可展示的任务。</div>
          <template v-else>
            <div class="enterprise-inline-actions extraction-task-tabs"><button v-for="task in tasks" :key="task.id" type="button" class="enterprise-button enterprise-button--quiet" :class="{ 'is-active': selectedTask.id === task.id }" @click="selectTask(task)"><FileCheck2 :size="14" /> {{ task.filename }}</button><button type="button" class="enterprise-button enterprise-button--quiet" :disabled="actionId === selectedBatch.id" @click="rerun(selectedBatch)"><RefreshCw :size="14" /> 重跑</button><button type="button" class="enterprise-button enterprise-button--quiet" :disabled="actionId === selectedBatch.id || ['success', 'completed_with_errors', 'cancelled'].includes(selectedBatch.status)" @click="cancel(selectedBatch)">取消批次</button></div>
            <div class="enterprise-detail-grid"><div class="enterprise-detail-cell"><span class="enterprise-detail-cell__label">任务状态</span><strong class="enterprise-detail-cell__value"><span :class="statusClass(selectedTask.status)">{{ selectedTask.status }}</span></strong></div><div class="enterprise-detail-cell"><span class="enterprise-detail-cell__label">原文文件</span><strong class="enterprise-detail-cell__value">{{ selectedTask.filename }}</strong></div><div class="enterprise-detail-cell"><span class="enterprise-detail-cell__label">证据</span><strong class="enterprise-detail-cell__value">{{ selectedTask.evidence?.length || 0 }} 条</strong></div><div class="enterprise-detail-cell"><span class="enterprise-detail-cell__label">校验错误</span><strong class="enterprise-detail-cell__value">{{ selectedTask.validation_errors?.length || 0 }} 条</strong></div></div>
            <form class="enterprise-form" @submit.prevent="revise"><div class="enterprise-field"><label for="revision-result">人工修订 JSON</label><textarea id="revision-result" v-model="revisionForm.result_json" class="enterprise-tall-input" /></div><div class="enterprise-field"><label for="revision-evidence">证据 JSON</label><textarea id="revision-evidence" v-model="revisionForm.evidence" /></div><button type="submit" class="enterprise-button enterprise-button--primary" :disabled="saving"><Save :size="14" /> 保存修订</button></form>
            <div class="enterprise-revision-list"><h3>修订记录</h3><div v-if="!revisions.length" class="enterprise-empty">暂无修订记录。</div><div v-for="revision in revisions" :key="revision.id" class="enterprise-revision-row"><span>v{{ revision.revision_no }} · {{ revision.revision_type }}</span><span>{{ revision.created_at }}</span></div></div>
          </template>
        </div>
      </section>
    </div>
  </main>
</template>

<style lang="less">
@import '@/assets/css/enterprise.less';

.enterprise-button.is-active {
  border-color: var(--main-300);
  background: var(--main-30);
  color: var(--main-800);
}

.enterprise-tall-input {
  min-height: 150px !important;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace !important;
}

.extraction-create {
  border-bottom: 1px solid var(--gray-150);
}

.extraction-template-list {
  margin-top: 18px;
}

.extraction-task-tabs {
  margin-bottom: 16px;
}

.enterprise-revision-list {
  margin-top: 22px;
  border-top: 1px solid var(--gray-150);
}

.enterprise-revision-list h3 {
  margin: 16px 0 10px;
  font-size: 13px;
}

.enterprise-revision-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 0;
  border-bottom: 1px solid var(--gray-150);
  color: var(--gray-600);
  font-size: 12px;
}
</style>
