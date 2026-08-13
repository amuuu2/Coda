<template>
  <div class="page-header" :class="{ 'page-header--bordered': showBorder }">
    <div v-if="loading" class="page-header-loading-bar-wrapper">
      <div class="page-header-loading-bar"></div>
    </div>
    <div class="page-header-left">
      <h1 class="page-header-title">{{ title }}</h1>
      <nav v-if="tabs.length > 0" class="page-header-tabs" :aria-label="ariaLabel">
        <template v-for="item in tabs" :key="item.key">
          <RouterLink
            v-if="item.path"
            :to="item.path"
            class="tab-item"
            :class="{ active: activeKey === item.key }"
            @click="emitChange(item)"
          >
            {{ item.label }}
          </RouterLink>
          <button
            v-else
            type="button"
            class="tab-item"
            :class="{ active: activeKey === item.key }"
            @click="emitChange(item)"
          >
            {{ item.label }}
          </button>
        </template>
      </nav>
    </div>
    <div v-if="$slots.info || $slots.actions" class="page-header-right">
      <slot name="info" />
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
import { RouterLink } from 'vue-router'

defineProps({
  title: { type: String, required: true },
  activeKey: { type: String, default: '' },
  tabs: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  showBorder: { type: Boolean, default: false },
  ariaLabel: { type: String, default: '视图切换' }
})

const emit = defineEmits(['update:activeKey', 'change'])

function emitChange(item) {
  emit('update:activeKey', item.key)
  emit('change', item)
}
</script>

<style scoped lang="less">
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  min-height: 72px;
  padding: 14px var(--page-padding) 13px;
  background-color: color-mix(in srgb, var(--gray-0) 94%, transparent);
  backdrop-filter: blur(12px);
  position: sticky;
  top: 0;
  z-index: 1000;

  &--bordered {
    border-bottom: 1px solid var(--gray-150);
  }
}

.page-header-left {
  display: flex;
  align-items: center;
  gap: 22px;
  min-width: 0;
}

.page-header-title {
  margin: 0;
  font-size: 21px;
  font-weight: 650;
  line-height: 1.2;
  color: var(--gray-1000);
  white-space: nowrap;
}

.page-header-tabs {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px;
  margin: 0;
  border: 1px solid var(--gray-150);
  border-radius: 7px;
  background: var(--gray-25);
  min-height: 34px;
  flex-shrink: 0;
}

.tab-item {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 12px;
  border: 1px solid transparent;
  border-radius: 5px;
  background: transparent;
  color: var(--gray-600);
  font-size: 13px;
  font-weight: 500;
  line-height: 1;
  text-decoration: none;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    color 0.2s ease;

  &:hover {
    color: var(--gray-900);
    background-color: var(--gray-50);
  }

  &.active {
    color: var(--gray-1000);
    background-color: var(--gray-0);
    border-color: var(--gray-150);
    font-weight: 600;
  }
}

.page-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

@media (max-width: 767px) {
  .page-header {
    min-height: auto;
    align-items: flex-start;
    padding-block: 12px;
  }

  .page-header-left {
    min-width: 0;
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .page-header-tabs {
    max-width: calc(100vw - 2 * var(--page-padding));
    overflow-x: auto;
  }

  .page-header-right {
    max-width: 50%;
    flex-wrap: wrap;
    justify-content: flex-end;
  }
}

.page-header-loading-bar-wrapper {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  z-index: 101;
  overflow: hidden;
  background: transparent;

  .page-header-loading-bar {
    height: 100%;
    background: var(--main-color);
    width: 30%;
    position: absolute;
    animation: page-header-loading-bar-anim 1.5s infinite linear;
  }
}

@keyframes page-header-loading-bar-anim {
  0% {
    left: -30%;
  }
  100% {
    left: 100%;
  }
}
</style>
