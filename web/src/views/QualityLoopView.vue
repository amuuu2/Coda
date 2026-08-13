<script setup>
import { computed, ref, unref } from 'vue'

import PageHeader from '@/components/shared/PageHeader.vue'
import QualityLoopPanel from '@/components/model-management/QualityLoopPanel.vue'

const qualityPanelRef = ref(null)
const activeStats = computed(() => unref(qualityPanelRef.value?.stats) || {})
const activeLoading = computed(() => Boolean(unref(qualityPanelRef.value?.loading)))
</script>

<template>
  <div class="quality-loop-view">
    <PageHeader title="Agent 质量评测" :loading="activeLoading" :show-border="true">
      <template #info>
        <div class="summary-strip">
          <span>{{ activeStats.samples || 0 }} 条测试问题</span>
          <span>{{ activeStats.candidates || 0 }} 个候选版本</span>
          <span>{{ activeStats.experiments || 0 }} 条评测记录</span>
        </div>
      </template>
    </PageHeader>

    <div class="quality-loop-content">
      <QualityLoopPanel ref="qualityPanelRef" />
    </div>
  </div>
</template>

<style lang="less" scoped>
.quality-loop-view {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  background: var(--gray-10);
  color: var(--gray-1000);
}

.quality-loop-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.summary-strip {
  display: flex;
  align-items: center;
  gap: 0;

  span {
    padding: 0 10px;
    border-right: 1px solid var(--gray-150);
    color: var(--gray-500);
    font-size: 11px;
    line-height: 18px;

    &:last-child {
      padding-right: 0;
      border-right: 0;
    }
  }
}
</style>
