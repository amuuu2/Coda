<script setup>
import { computed, ref } from 'vue'

import PageHeader from '@/components/shared/PageHeader.vue'
import QualityLoopPanel from '@/components/model-management/QualityLoopPanel.vue'

const qualityPanelRef = ref(null)
const activeStats = computed(() => qualityPanelRef.value?.stats || {})
const activeLoading = computed(() => qualityPanelRef.value?.loading || false)
</script>

<template>
  <div class="quality-loop-view">
    <PageHeader title="质量闭环" :loading="activeLoading" :show-border="true">
      <template #info>
        <div class="summary-strip">
          <span>{{ activeStats.samples || 0 }} 个 Replay 样本</span>
          <span>{{ activeStats.candidates || 0 }} 个候选</span>
          <span>{{ activeStats.experiments || 0 }} 次实验</span>
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
  background: var(--gray-0);
  color: var(--gray-1000);
}

.quality-loop-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.summary-strip {
  display: flex;
  gap: 8px;

  span {
    padding: 6px 10px;
    border: 1px solid var(--gray-100);
    border-radius: 7px;
    background: var(--gray-10);
    color: var(--gray-700);
    font-size: 12px;
    line-height: 18px;
  }
}
</style>
