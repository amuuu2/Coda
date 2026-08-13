<template>
  <div class="stats-overview-container">
    <div class="stats-grid">
      <div class="stat-card primary">
        <div class="stat-icon">
          <MessageCircle class="icon" />
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ basicStats?.total_conversations || 0 }}</div>
          <div class="stat-label">累计会话</div>
          <div class="stat-trend" v-if="basicStats?.conversation_trend">
            <TrendingUp v-if="basicStats.conversation_trend > 0" class="trend-icon up" />
            <TrendingDown v-else-if="basicStats.conversation_trend < 0" class="trend-icon down" />
            <span class="trend-text">{{ Math.abs(basicStats.conversation_trend) }}%</span>
          </div>
        </div>
      </div>

      <div class="stat-card success">
        <div class="stat-icon">
          <Activity class="icon" />
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ basicStats?.active_conversations || 0 }}</div>
          <div class="stat-label">活跃对话</div>
        </div>
      </div>

      <div class="stat-card info">
        <div class="stat-icon">
          <Mail class="icon" />
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ basicStats?.total_messages || 0 }}</div>
          <div class="stat-label">总消息数</div>
        </div>
      </div>

      <div class="stat-card warning">
        <div class="stat-icon">
          <Users class="icon" />
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ basicStats?.total_users || 0 }}</div>
          <div class="stat-label">用户数</div>
        </div>
      </div>

      <div class="stat-card secondary clickable" @click="handleFeedbackClick">
        <div class="stat-icon">
          <BarChart3 class="icon" />
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ basicStats?.feedback_stats?.total_feedbacks || 0 }}</div>
          <div class="stat-label">总反馈数</div>
        </div>
      </div>

      <div class="stat-card" :class="getSatisfactionClass()">
        <div class="stat-icon">
          <Heart class="icon" />
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ basicStats?.feedback_stats?.satisfaction_rate || 0 }}%</div>
          <div class="stat-label">满意度</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  MessageCircle,
  Activity,
  Mail,
  Users,
  BarChart3,
  Heart,
  TrendingUp,
  TrendingDown
} from 'lucide-vue-next'

// Props
const props = defineProps({
  basicStats: {
    type: Object,
    default: () => ({})
  }
})

// Emits
const emit = defineEmits(['open-feedback'])

// Methods
const handleFeedbackClick = () => {
  emit('open-feedback')
}

// Methods
const getSatisfactionClass = () => {
  const rate = props.basicStats?.feedback_stats?.satisfaction_rate || 0
  if (rate >= 80) return 'satisfaction-high'
  if (rate >= 60) return 'satisfaction-medium'
  return 'satisfaction-low'
}
</script>

<style lang="less" scoped>
// 使用 dashboard.css 中定义的样式，这里只需要导入
@import '@/assets/css/dashboard.css';

/* Stats Overview Component - 统计概览组件样式 */
.stats-overview-container {
  margin-top: 0;
  padding-top: 18px;

  .stats-grid {
    display: grid;
    padding: 0 var(--page-padding);
    grid-template-columns: repeat(6, 1fr);
    gap: 0;
    border: 1px solid var(--gray-150);
    border-radius: 8px;
    background: var(--gray-0);
    overflow: hidden;

    .stat-card {
      background: transparent;
      border-radius: 0;
      padding: 18px;
      border: 0;
      border-right: 1px solid var(--gray-100);
      transition: all 0.2s ease;
      display: flex;
      flex-direction: row;
      align-items: center;
      text-align: left;
      min-height: 80px;
      justify-content: flex-start;

      &:hover {
        background: var(--gray-25);
        box-shadow: none;
      }

      &:last-child {
        border-right: 0;
      }

      &.primary {
        .stat-icon {
          background-color: var(--color-primary-50);
          color: var(--main-color);
        }
      }

      &.success {
        .stat-icon {
          background-color: var(--color-success-50);
          color: var(--color-success-700);
        }
      }

      &.info {
        .stat-icon {
          background-color: var(--color-info-50);
          color: var(--color-info-700);
        }
      }

      &.warning {
        .stat-icon {
          background-color: var(--color-warning-50);
          color: var(--color-warning-700);
        }
      }

      &.secondary {
        .stat-icon {
          background-color: var(--color-accent-50);
          color: var(--color-accent-700);
        }
      }

      &.clickable {
        cursor: pointer;
      }

      &.satisfaction-high {
        .stat-icon {
          background-color: var(--color-success-50);
          color: var(--color-success-700);
        }
      }

      &.satisfaction-medium {
        .stat-icon {
          background-color: var(--color-warning-50);
          color: var(--color-warning-700);
        }
      }

      &.satisfaction-low {
        .stat-icon {
          background-color: var(--color-error-50);
          color: var(--color-error-700);
        }
      }

      .stat-icon {
        width: 34px;
        height: 34px;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-right: 12px;
        flex-shrink: 0;

        .icon {
          width: 17px;
          height: 17px;
        }
      }

      .stat-content {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: flex-start;

        .stat-value {
          font-family: 'SFMono-Regular', Consolas, monospace;
          font-size: 20px;
          font-weight: 650;
          color: var(--gray-1000);
          line-height: 1.1;
          margin-bottom: 3px;
        }

        .stat-label {
          font-size: 13px;
          color: var(--gray-600);
          font-weight: 500;
          margin-bottom: 8px;
        }

        .stat-trend {
          display: flex;
          align-items: center;
          gap: 4px;
          margin-top: 4px;

          .trend-icon {
            width: 14px;
            height: 14px;

            &.up {
              color: var(--color-success-700);
            }

            &.down {
              color: var(--color-error-700);
            }
          }

          .trend-text {
            font-size: 12px;
            font-weight: 500;
            color: var(--gray-600);
          }
        }
      }
    }
  }
}

/* Stats Overview 响应式设计 */
@media (max-width: 1200px) {
  .stats-overview-container {
    .stats-grid {
      grid-template-columns: repeat(3, 1fr);
      gap: 0;

      .stat-card:nth-child(3n) {
        border-right: 0;
      }

      .stat-card:nth-child(-n + 3) {
        border-bottom: 1px solid var(--gray-100);
      }
    }
  }
}

@media (max-width: 768px) {
  .stats-overview-container {
    .stats-grid {
      grid-template-columns: repeat(2, 1fr);
      gap: 0;

      .stat-card,
      .stat-card:nth-child(3n) {
        border-right: 1px solid var(--gray-100);
      }

      .stat-card:nth-child(2n) {
        border-right: 0;
      }

      .stat-card:nth-child(-n + 4) {
        border-bottom: 1px solid var(--gray-100);
      }

      .stat-card {
        padding: 16px;
        min-height: 80px;

        .stat-icon {
          width: 36px;
          height: 36px;
          margin-right: 12px;

          .icon {
            width: 18px;
            height: 18px;
          }
        }

        .stat-content {
          .stat-value {
            font-size: 20px;
          }

          .stat-label {
            font-size: 12px;
          }
        }
      }
    }
  }
}
</style>
