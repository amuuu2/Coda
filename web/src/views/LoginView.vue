<template>
  <div class="login-view" :class="{ 'has-alert': serverStatus === 'error' }">
    <!-- 服务状态提示 -->
    <div v-if="serverStatus === 'error'" class="server-status-alert">
      <div class="alert-content">
        <exclamation-circle-icon class="alert-icon" size="20" />
        <div class="alert-text">
          <div class="alert-title">服务端连接失败</div>
          <div class="alert-message">{{ serverError }}</div>
        </div>
        <a-button type="link" size="small" @click="checkServerHealth" :loading="healthChecking">
          重试
        </a-button>
      </div>
    </div>

    <nav class="login-navbar">
      <div class="navbar-content">
        <button class="brand-container" type="button" aria-label="返回首页" @click="goHome">
          <img v-if="brandLogo" :src="brandLogo" :alt="brandName" class="brand-logo" />
          <span class="brand-text">
            <span v-if="brandOrgName" class="brand-org">{{ brandOrgName }}</span>
            <span v-if="brandOrgName && brandName !== brandOrgName" class="brand-separator"></span>
            <span class="brand-main">{{ brandName }}</span>
          </span>
        </button>
        <span class="navbar-note">Knowledge workspace</span>
      </div>
    </nav>

    <main class="login-main">
      <div class="login-card">
        <div class="card-side is-image">
          <img :src="loginBgImage" alt="Coda 知识工作区" class="login-bg-image" />
          <div class="image-overlay" aria-hidden="true"></div>
          <div class="image-content">
            <p class="image-index">Coda / Workspace</p>
            <h2>让知识成为<br />可持续工作的系统。</h2>
            <p>连接知识库、知识图谱与智能体，在一个清晰的工作区内完成检索、推理与协作。</p>
            <div class="capability-list" aria-label="平台能力">
              <span>知识检索</span>
              <span>图谱推理</span>
              <span>智能体协作</span>
            </div>
          </div>
        </div>

        <!-- 右侧表单 -->
        <div class="card-side is-form">
          <div class="form-wrapper">
            <header class="form-header">
              <p class="form-kicker">{{ isFirstRun ? 'System setup' : 'Welcome back' }}</p>
              <h1 v-if="isFirstRun" class="init-title">创建超级管理员</h1>
              <h1 v-else class="welcome-text">登录 Coda</h1>
              <p class="form-description">
                {{ isFirstRun ? '完成初始账户设置后即可进入工作区。' : '使用你的账户继续访问知识工作区。' }}
              </p>
            </header>

            <div class="login-content" :class="{ 'is-initializing': isFirstRun }">
              <!-- 初始化管理员表单 -->
              <div v-if="isFirstRun" class="login-form login-form--init">
                <a-form :model="adminForm" @finish="handleInitialize" layout="vertical">
                  <a-form-item
                    label="UID"
                    name="uid"
                    :rules="[
                      { required: true, message: '请输入UID' },
                      {
                        pattern: /^[a-zA-Z0-9_]+$/,
                        message: 'UID只能包含字母、数字和下划线'
                      },
                      {
                        min: 3,
                        max: 20,
                        message: 'UID长度必须在3-20个字符之间'
                      }
                    ]"
                  >
                    <a-input
                      v-model:value="adminForm.uid"
                      placeholder="请输入UID（3-20个字符）"
                      :maxlength="20"
                    />
                  </a-form-item>

                  <a-form-item
                    label="手机号（可选）"
                    name="phone_number"
                    :rules="[
                      {
                        validator: async (rule, value) => {
                          if (!value || value.trim() === '') {
                            return // 空值允许
                          }
                          const phoneRegex = /^1[3-9]\d{9}$/
                          if (!phoneRegex.test(value)) {
                            throw new Error('请输入正确的手机号格式')
                          }
                        }
                      }
                    ]"
                  >
                    <a-input
                      v-model:value="adminForm.phone_number"
                      placeholder="可用于登录，可不填写"
                      :max-length="11"
                    />
                  </a-form-item>

                  <a-form-item
                    label="密码"
                    name="password"
                    :rules="[
                      { required: true, message: '请输入密码' },
                      {
                        min: MIN_PASSWORD_LENGTH,
                        message: `密码至少需要 ${MIN_PASSWORD_LENGTH} 个字符`
                      }
                    ]"
                  >
                    <a-input-password
                      v-model:value="adminForm.password"
                      prefix-icon="lock"
                      :minlength="MIN_PASSWORD_LENGTH"
                    />
                  </a-form-item>

                  <a-form-item
                    label="确认密码"
                    name="confirmPassword"
                    :rules="[
                      { required: true, message: '请确认密码' },
                      { validator: validateConfirmPassword }
                    ]"
                  >
                    <a-input-password
                      v-model:value="adminForm.confirmPassword"
                      prefix-icon="lock"
                    />
                  </a-form-item>

                  <a-form-item v-if="showAgreementConsent" class="agreement-form-item">
                    <div class="agreement-row">
                      <a-checkbox v-model:checked="agreementAccepted">
                        登录即代表同意
                        <a
                          class="agreement-link"
                          :href="userAgreementUrl"
                          target="_blank"
                          rel="noopener noreferrer"
                          @click.stop
                          >《用户协议》</a
                        >
                        <a
                          class="agreement-link"
                          :href="privacyPolicyUrl"
                          target="_blank"
                          rel="noopener noreferrer"
                          @click.stop
                          >《隐私协议》</a
                        >
                      </a-checkbox>
                    </div>
                  </a-form-item>

                  <a-form-item>
                    <a-button type="primary" html-type="submit" :loading="loading" block
                      >创建管理员账户</a-button
                    >
                  </a-form-item>
                </a-form>
              </div>

              <!-- 登录表单 -->
              <div v-else class="login-form">
                <a-form :model="loginForm" @finish="handleLogin" layout="vertical">
                  <a-form-item
                    label="登录账号"
                    name="loginId"
                    :rules="[{ required: true, message: '请输入UID或手机号' }]"
                  >
                    <a-input v-model:value="loginForm.loginId" placeholder="UID或手机号">
                      <template #prefix>
                        <user-icon size="18" />
                      </template>
                    </a-input>
                  </a-form-item>

                  <a-form-item
                    label="密码"
                    name="password"
                    :rules="[{ required: true, message: '请输入密码' }]"
                  >
                    <a-input-password v-model:value="loginForm.password">
                      <template #prefix>
                        <lock-icon size="18" />
                      </template>
                    </a-input-password>
                  </a-form-item>

                  <a-form-item v-if="showAgreementConsent" class="agreement-form-item">
                    <div class="agreement-row">
                      <a-checkbox v-model:checked="agreementAccepted">
                        登录即代表同意
                        <a
                          class="agreement-link"
                          :href="userAgreementUrl"
                          target="_blank"
                          rel="noopener noreferrer"
                          @click.stop
                          >《用户协议》</a
                        >
                        <a
                          class="agreement-link"
                          :href="privacyPolicyUrl"
                          target="_blank"
                          rel="noopener noreferrer"
                          @click.stop
                          >《隐私协议》</a
                        >
                      </a-checkbox>
                    </div>
                  </a-form-item>

                  <a-form-item>
                    <a-button
                      type="primary"
                      html-type="submit"
                      :loading="loading"
                      :disabled="isLocked"
                      block
                      size="large"
                    >
                      <span v-if="isLocked">账户已锁定 {{ formatTime(lockRemainingTime) }}</span>
                      <span v-else>登录</span>
                    </a-button>
                  </a-form-item>
                </a-form>

                <!-- OIDC 登录选项  -->
                <div v-if="oidcChecking || oidcEnabled" class="third-party-login">
                  <div class="divider">
                    <span>或使用以下方式登录</span>
                  </div>
                  <div class="login-icons">
                    <!-- 检查中显示骨架屏 -->
                    <div v-if="oidcChecking" class="login-skeleton">
                      <a-skeleton-button block size="large" :active="true" />
                    </div>
                    <!-- 检查完成后显示按钮 -->
                    <a-button
                      v-else
                      type="default"
                      size="large"
                      block
                      :loading="oidcLoading"
                      @click="handleOIDCLogin"
                    >
                      <template #icon>
                        <key-icon size="18" />
                      </template>
                      {{ oidcButtonText }}
                    </a-button>
                  </div>
                </div>
              </div>

              <!-- 错误提示 -->
              <div v-if="errorMessage" class="error-message">
                {{ errorMessage }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <footer class="page-footer">
      <div class="footer-links">
        <a href="https://github.com/amuuu2/Coda" target="_blank" rel="noopener noreferrer"
          >使用帮助</a
        >
      </div>
      <div class="copyright">
        &copy; {{ new Date().getFullYear() }} {{ brandName }}. All Rights Reserved.
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useInfoStore } from '@/stores/info'
import { useAgentStore } from '@/stores/agent'
import { message } from 'ant-design-vue'
import { healthApi } from '@/apis/system_api'
import { authApi } from '@/apis/auth_api'
import {
  User as UserIcon,
  Lock as LockIcon,
  Key as KeyIcon,
  AlertCircle as ExclamationCircleIcon
} from 'lucide-vue-next'
import { tryAutoStartOIDC, sanitizeRedirect } from '@/utils/oidcAutoStart'
import { MIN_PASSWORD_LENGTH } from '@/utils/passwordValidation'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const infoStore = useInfoStore()
const agentStore = useAgentStore()

// 品牌展示数据
const loginBgImage = computed(() => {
  return infoStore.organization?.login_bg || '/login-bg.jpg'
})
const brandLogo = computed(() => {
  return infoStore.organization?.logo || ''
})
const brandOrgName = computed(() => {
  return infoStore.organization?.name?.trim() || ''
})
const brandName = computed(() => {
  const orgName = brandOrgName.value
  const brandNameRaw = infoStore.branding?.name?.trim() || 'Coda'

  if (orgName && brandNameRaw && orgName !== brandNameRaw) {
    return brandNameRaw
  }

  return orgName || brandNameRaw
})
const userAgreementUrl = computed(() => {
  return infoStore.footer?.user_agreement_url?.trim() || ''
})
const privacyPolicyUrl = computed(() => {
  return infoStore.footer?.privacy_policy_url?.trim() || ''
})
const showAgreementConsent = computed(() => {
  return Boolean(userAgreementUrl.value && privacyPolicyUrl.value)
})

// 状态
const isFirstRun = ref(false)
const loading = ref(false)
const errorMessage = ref('')
const agreementAccepted = ref(false)
const serverStatus = ref('loading')
const serverError = ref('')
const healthChecking = ref(false)

// OIDC 相关状态
const oidcEnabled = ref(false)
const oidcLoading = ref(false)
const oidcChecking = ref(true)
const oidcButtonText = ref('OIDC 登录')

// 登录锁定相关状态
const isLocked = ref(false)
const lockRemainingTime = ref(0)
const lockCountdown = ref(null)

// 登录表单
const loginForm = reactive({
  loginId: '', // 支持uid或phone_number登录
  password: ''
})

// 管理员初始化表单
const adminForm = reactive({
  uid: '', // 改为直接输入uid
  password: '',
  confirmPassword: '',
  phone_number: '' // 手机号字段（可选）
})

const goHome = () => {
  router.push('/')
}

// 清理倒计时器
const clearLockCountdown = () => {
  if (lockCountdown.value) {
    clearInterval(lockCountdown.value)
    lockCountdown.value = null
  }
}

// 启动锁定倒计时
const startLockCountdown = (remainingSeconds) => {
  clearLockCountdown()
  isLocked.value = true
  lockRemainingTime.value = remainingSeconds

  lockCountdown.value = setInterval(() => {
    lockRemainingTime.value--
    if (lockRemainingTime.value <= 0) {
      clearLockCountdown()
      isLocked.value = false
      errorMessage.value = ''
    }
  }, 1000)
}

// 格式化时间显示
const formatTime = (seconds) => {
  if (seconds < 60) {
    return `${seconds}秒`
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60
    return `${minutes}分${remainingSeconds}秒`
  } else if (seconds < 86400) {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}小时${minutes}分钟`
  } else {
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    return `${days}天${hours}小时`
  }
}

// 密码确认验证
const validateConfirmPassword = async (rule, value) => {
  if (value === '') {
    throw new Error('请确认密码')
  }
  if (value !== adminForm.password) {
    throw new Error('两次输入的密码不一致')
  }
}

const ensureAgreementAccepted = () => {
  if (!showAgreementConsent.value || agreementAccepted.value) {
    return true
  }

  const warningMessage = '请先阅读并同意《用户协议》《隐私协议》'
  message.warning(warningMessage)
  return false
}

// 处理登录
const handleLogin = async () => {
  // 如果当前被锁定，不允许登录
  if (isLocked.value) {
    message.warning(`账户被锁定，请等待 ${formatTime(lockRemainingTime.value)}`)
    return
  }

  if (!ensureAgreementAccepted()) {
    return
  }

  try {
    loading.value = true
    errorMessage.value = ''
    clearLockCountdown()

    await userStore.login({
      loginId: loginForm.loginId,
      password: loginForm.password
    })

    message.success('登录成功')

    // 获取重定向路径
    const redirectPath = sessionStorage.getItem('redirect') || '/'
    sessionStorage.removeItem('redirect') // 清除重定向信息

    // 根据用户角色决定重定向目标
    if (redirectPath === '/') {
      // 统一跳转到聊天页面（管理员与普通用户共享同一聊天界面）
      try {
        await agentStore.initialize()
        router.push('/agent')
      } catch (error) {
        console.error('获取智能体信息失败:', error)
        router.push('/agent')
      }
    } else {
      // 跳转到其他预设的路径
      router.push(redirectPath)
    }
  } catch (error) {
    console.error('登录失败:', error)

    // 检查是否是锁定错误（HTTP 423）
    if (error.status === 423) {
      // 尝试从响应头中获取剩余时间
      let remainingTime = 0
      if (error.headers && error.headers.get) {
        const lockRemainingHeader = error.headers.get('X-Lock-Remaining')
        if (lockRemainingHeader) {
          remainingTime = parseInt(lockRemainingHeader)
        }
      }

      // 如果没有从头中获取到，尝试从错误消息中解析
      if (remainingTime === 0) {
        const lockTimeMatch = error.message.match(/(\d+)\s*秒/)
        if (lockTimeMatch) {
          remainingTime = parseInt(lockTimeMatch[1])
        }
      }

      if (remainingTime > 0) {
        startLockCountdown(remainingTime)
        errorMessage.value = `由于多次登录失败，账户已被锁定 ${formatTime(remainingTime)}`
      } else {
        errorMessage.value = error.message || '账户被锁定，请稍后再试'
      }
    } else {
      errorMessage.value = error.message || '登录失败，请检查用户名和密码'
    }
  } finally {
    loading.value = false
  }
}

// 处理 OIDC 登录
const handleOIDCLogin = async () => {
  if (!ensureAgreementAccepted()) {
    return
  }

  try {
    oidcLoading.value = true
    errorMessage.value = ''

    // 获取 OIDC 登录 URL
    const response = await authApi.getOIDCLoginUrl()
    if (response.login_url) {
      // 保存当前路径，以便登录后返回
      const redirectPath =
        sessionStorage.getItem('redirect') || router.currentRoute.value.query.redirect || '/'
      sessionStorage.setItem('oidc_redirect', redirectPath)

      // 跳转到 OIDC Provider
      window.location.href = response.login_url
    } else {
      errorMessage.value = '获取 OIDC 登录地址失败'
    }
  } catch (error) {
    console.error('OIDC 登录失败:', error)
    errorMessage.value = error.message || 'OIDC 登录失败，请重试'
  } finally {
    oidcLoading.value = false
  }
}

// 检查 OIDC 配置
const checkOIDCConfig = async () => {
  oidcChecking.value = true
  try {
    const config = await authApi.getOIDCConfig()
    oidcEnabled.value = config.enabled
    if (config.provider_name) {
      oidcButtonText.value = config.provider_name
    }
    return config
  } catch (error) {
    console.error('检查 OIDC 配置失败:', error)
    oidcEnabled.value = false
    return null
  } finally {
    oidcChecking.value = false
  }
}

// 处理初始化管理员
const handleInitialize = async () => {
  if (!ensureAgreementAccepted()) {
    return
  }

  try {
    loading.value = true
    errorMessage.value = ''

    if (adminForm.password !== adminForm.confirmPassword) {
      errorMessage.value = '两次输入的密码不一致'
      return
    }

    await userStore.initialize({
      uid: adminForm.uid,
      password: adminForm.password,
      phone_number: adminForm.phone_number || null // 空字符串转为null
    })

    message.success('管理员账户创建成功')
    router.push('/')
  } catch (error) {
    console.error('初始化失败:', error)
    errorMessage.value = error.message || '初始化失败，请重试'
  } finally {
    loading.value = false
  }
}

// 检查是否是首次运行
const checkFirstRunStatus = async () => {
  try {
    loading.value = true
    const isFirst = await userStore.checkFirstRun()
    isFirstRun.value = isFirst
  } catch (error) {
    console.error('检查首次运行状态失败:', error)
    errorMessage.value = '系统出错，请稍后重试'
  } finally {
    loading.value = false
  }
}

// 检查服务器健康状态
const checkServerHealth = async () => {
  try {
    healthChecking.value = true
    const response = await healthApi.checkHealth()
    if (response.status === 'ok') {
      serverStatus.value = 'ok'
    } else {
      serverStatus.value = 'error'
      serverError.value = response.message || '服务端状态异常'
    }
  } catch (error) {
    console.error('检查服务器健康状态失败:', error)
    serverStatus.value = 'error'
    serverError.value = error.message || '无法连接到服务端，请检查网络连接'
  } finally {
    healthChecking.value = false
  }
}

// 组件挂载时
onMounted(async () => {
  // 如果已登录，按 redirect 参数跳转（不固定跳首页）
  if (userStore.isLoggedIn) {
    router.push(sanitizeRedirect(route.query.redirect))
    return
  }

  // 显示 OIDC 认证失败的错误信息（由后端重定向携带）
  if (route.query.oidc_error) {
    errorMessage.value = String(route.query.oidc_error)
  }

  // 首先检查服务器健康状态
  await checkServerHealth()

  // 检查是否是首次运行
  await checkFirstRunStatus()

  // 如果处于首次运行状态，不需要 OIDC 自动登录
  if (isFirstRun.value) {
    return
  }

  // 检查 OIDC 配置完成后，尝试自动触发 OIDC 登录（跨系统跳转场景）
  const config = await checkOIDCConfig()
  if (config && config.enabled) {
    const autoStarted = await tryAutoStartOIDC(async () => await authApi.getOIDCLoginUrl(), config)
    // 如果已发起 OIDC 跳转，页面会被重定向，不需要继续
    if (autoStarted) return
  }
})

// 组件卸载时清理定时器
onUnmounted(() => {
  clearLockCountdown()
})
</script>

<style lang="less" scoped>
.login-view {
  min-height: 100vh;
  width: 100%;
  position: relative;
  display: flex;
  flex-direction: column;
  background-color: var(--gray-10);
  background-image: radial-gradient(var(--gray-200) 1px, transparent 1px);
  background-size: 24px 24px;

  &.has-alert {
    padding-top: 60px;
  }
}

/* Unified Navbar */
.login-navbar {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  padding: 32px 0;
  z-index: 10;

  .navbar-content {
    max-width: 1500px; /* Constraint the width */
    margin: 0 auto;
    padding: 0 40px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    .brand-container {
      display: flex;
      align-items: center;
      gap: 12px;
    }
  }
}

.brand-text {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  line-height: 1;
  display: flex;
  align-items: center;
  gap: 12px;

  .brand-org {
    color: var(--gray-700);
    font-weight: 600;
  }

  .brand-separator {
    width: 4px;
    height: 4px;
    background-color: var(--gray-400);
    border-radius: 50%;
    font-weight: 600;
  }

  .brand-main {
    color: var(--main-color);
    font-weight: 600;
  }
}

.brand-logo {
  height: 32px;
  width: auto;
  object-fit: contain;
}

.top-logo {
  height: 32px;
  width: auto;
  object-fit: contain;
}

.back-home-btn {
  color: var(--gray-600);
  font-size: 14px;
  &:hover {
    color: var(--main-color);
    background-color: transparent;
  }
}

/* Main Content: Card Layout */
.login-main {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  padding-top: 80px; /* Add space for navbar */
}

.login-card {
  width: 900px;
  max-width: 95vw;
  height: 560px;
  background: var(--gray-0);
  border-radius: 16px;
  box-shadow: 0 0px 40px var(--shadow-1);
  display: flex;
  overflow: hidden;
}

.card-side {
  position: relative;
}

/* Image Side */
.card-side.is-image {
  flex: 1.4;
  background-color: var(--main-10);
  overflow: hidden;

  .login-bg-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center;
  }
}

/* Form Side */
.card-side.is-form {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.form-wrapper {
  width: 100%;
  max-width: 320px;
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.form-header {
  text-align: left;
  .welcome-text {
    font-size: 14px;
    font-weight: 600;
    color: var(--gray-500);
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }
  .init-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--main-color);
    margin: 0;
    line-height: 1.4;
  }
}

.login-form {
  :deep(.ant-input-affix-wrapper) {
    padding: 10px 12px;
    border-radius: 8px;
  }
  :deep(.ant-btn) {
    height: 44px;
    font-size: 16px;
    border-radius: 8px;
  }
  :deep(.ant-input-prefix) {
    margin-right: 8px;
    color: var(--gray-500);
  }
}

.login-form.login-form--init :deep(.ant-form-item) {
  margin-bottom: 14px;
}

.third-party-login {
  margin-top: 16px;
  .divider {
    position: relative;
    text-align: center;
    margin: 24px 0 16px;
    &::before,
    &::after {
      content: '';
      position: absolute;
      top: 50%;
      width: 30%;
      height: 1px;
      background-color: var(--gray-200);
    }
    &::before {
      left: 0;
    }
    &::after {
      right: 0;
    }
    span {
      display: inline-block;
      padding: 0 8px;
      background-color: var(--gray-0);
      color: var(--gray-400);
      font-size: 12px;
    }
  }

  .login-icons {
    :deep(.ant-btn) {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      border-color: var(--gray-300);
      color: var(--gray-700);

      &:hover {
        border-color: var(--main-color);
        color: var(--main-color);
        background-color: var(--main-10);
      }

      .anticon,
      svg {
        color: var(--main-color);
      }
    }
  }

  /* 修复：添加骨架屏样式 */
  .login-skeleton {
    :deep(.ant-skeleton-button) {
      width: 100% !important;
      height: 44px;
      border-radius: 8px;
    }
  }
}

.agreement-form-item {
  margin-bottom: 12px;
}

.agreement-row {
  font-size: 13px;
  color: var(--gray-600);
  line-height: 1.6;

  :deep(.ant-checkbox-wrapper) {
    display: inline-flex;
    align-items: flex-start;
  }

  :deep(.ant-checkbox + span) {
    padding-inline-start: 8px;
  }
}

.agreement-link {
  color: var(--main-color);

  &:hover {
    text-decoration: underline;
  }
}

.error-message {
  margin-top: 16px;
  padding: 10px 12px;
  background-color: var(--color-error-50);
  border: 1px solid color-mix(in srgb, var(--color-error-500) 25%, transparent);
  border-radius: 6px;
  color: var(--color-error-700);
  font-size: 13px;
  text-align: center;
}

/* Page Footer */
.page-footer {
  padding: 24px;
  text-align: center;
}

.footer-links {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-bottom: 8px;

  a {
    color: var(--gray-500);
    font-size: 13px;
    &:hover {
      color: var(--main-color);
    }
  }

  .divider {
    color: var(--gray-300);
    font-size: 12px;
  }
}

.copyright {
  font-size: 12px;
  color: var(--gray-400);
}

/* Server Status Alert */
.server-status-alert {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  padding: 12px 20px;
  background: var(--color-error-500);
  color: var(--gray-0);
  z-index: 1000;

  .alert-content {
    display: flex;
    align-items: center;
    max-width: 1500px;
    margin: 0 auto;

    .alert-icon {
      font-size: 20px;
      margin-right: 12px;
      color: var(--gray-0);
    }

    .alert-text {
      flex: 1;

      .alert-title {
        font-weight: 600;
        font-size: 16px;
        margin-bottom: 2px;
      }

      .alert-message {
        font-size: 14px;
        opacity: 0.9;
      }
    }

    :deep(.ant-btn-link) {
      color: var(--gray-0);
      border-color: var(--gray-0);

      &:hover {
        color: var(--gray-0);
        background-color: color-mix(in srgb, var(--gray-0) 10%, transparent);
      }
    }
  }
}

/* Responsive */
@media (max-width: 1280px) {
  .login-navbar .navbar-content {
    padding: 0 40px;
  }
}

@media (max-width: 768px) {
  .login-navbar .navbar-content {
    padding: 0 20px;
  }

  .brand-text {
    font-size: 20px;
  }

  .login-card {
    flex-direction: column;
    height: auto;
    max-height: none;
    width: 100%;
    margin-top: 20px;
  }

  .card-side.is-image {
    display: none;
  }

  .card-side.is-form {
    padding: 40px 20px;
  }
}
</style>

<style lang="less" scoped>
/* 登录页延续首页的编辑式语言，表单保持稳定、明确且可扫描。 */
.login-view {
  min-height: 100dvh;
  background: var(--gray-10);
  background-image: none;

  &.has-alert {
    padding-top: 64px;
  }
}

.login-navbar {
  position: relative;
  flex: 0 0 auto;
  min-height: 72px;
  padding: 0;
  border-bottom: 1px solid var(--gray-150);
  background: var(--gray-10);

  .navbar-content {
    width: 100%;
    max-width: 1440px;
    min-height: 72px;
    padding: 0 40px;
  }
}

.brand-container {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;

  &:focus-visible {
    outline: 2px solid var(--main-300);
    outline-offset: 4px;
    border-radius: 4px;
  }
}

.brand-logo {
  width: 30px;
  height: 30px;
  border-radius: 6px;
  object-fit: contain;
}

.brand-text {
  gap: 10px;
  font-size: 15px;

  .brand-org,
  .brand-main {
    color: var(--gray-1000);
    font-weight: 650;
  }

  .brand-separator {
    width: 1px;
    height: 14px;
    border-radius: 0;
    background: var(--gray-200);
  }

  .brand-main {
    color: var(--gray-600);
    font-weight: 500;
  }
}

.navbar-note {
  color: var(--gray-500);
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.login-main {
  align-items: stretch;
  padding: 0;
}

.login-card {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(430px, 0.92fr);
  width: 100%;
  max-width: none;
  min-height: calc(100dvh - 72px - 61px);
  height: auto;
  margin: 0;
  overflow: visible;
  border-radius: 0;
  background: var(--gray-10);
  box-shadow: none;
}

.card-side.is-image {
  position: relative;
  display: flex;
  align-items: flex-end;
  min-height: 620px;
  padding: clamp(48px, 7vw, 96px);
  overflow: hidden;
  background: var(--gray-900);
  isolation: isolate;

  .login-bg-image {
    position: absolute;
    inset: 0;
    z-index: -2;
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center;
    filter: grayscale(1) contrast(0.9) brightness(0.58);
    transform: scale(1.01);
  }
}

.image-overlay {
  position: absolute;
  inset: 0;
  z-index: -1;
  background: rgb(16 17 17 / 0.62);
}

.image-content {
  width: min(100%, 620px);
  color: #f8f8f6;

  h2 {
    margin: 20px 0 24px;
    font-family: 'Iowan Old Style', 'Palatino Linotype', 'Songti SC', 'Noto Serif CJK SC', serif;
    font-size: clamp(42px, 4.5vw, 68px);
    font-weight: 600;
    line-height: 1.08;
    letter-spacing: 0;
    text-wrap: balance;
  }

  > p:not(.image-index) {
    max-width: 500px;
    margin: 0;
    color: rgb(248 248 246 / 0.72);
    font-size: 15px;
    line-height: 1.8;
    text-wrap: pretty;
  }
}

.image-index {
  margin: 0;
  color: rgb(248 248 246 / 0.62);
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.capability-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 24px;
  margin-top: 36px;
  padding-top: 20px;
  border-top: 1px solid rgb(255 255 255 / 0.18);
  color: rgb(248 248 246 / 0.72);
  font-size: 12px;

  span::before {
    content: '—';
    margin-right: 8px;
    color: rgb(248 248 246 / 0.42);
  }
}

.card-side.is-form {
  align-items: center;
  padding: 72px clamp(40px, 7vw, 112px);
  background: var(--gray-0);
}

.form-wrapper {
  width: min(100%, 420px);
  max-width: none;
  gap: 34px;
}

.form-header {
  text-align: left;

  .welcome-text,
  .init-title {
    margin: 0;
    color: var(--gray-1000);
    font-family: 'Iowan Old Style', 'Palatino Linotype', 'Songti SC', 'Noto Serif CJK SC', serif;
    font-size: clamp(32px, 3vw, 44px);
    font-weight: 600;
    line-height: 1.14;
    text-transform: none;
    letter-spacing: 0;
  }
}

.form-kicker {
  margin: 0 0 14px;
  color: var(--gray-500);
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.form-description {
  margin: 14px 0 0;
  color: var(--gray-500);
  font-size: 14px;
  line-height: 1.7;
  letter-spacing: 0;
}

.login-content,
.login-form {
  width: 100%;
}

.login-form {
  :deep(.ant-form-item) {
    margin-bottom: 22px;
  }

  :deep(.ant-form-item-label > label) {
    height: auto;
    color: var(--gray-700);
    font-size: 13px;
    font-weight: 600;
  }

  :deep(.ant-input),
  :deep(.ant-input-affix-wrapper) {
    min-height: 46px;
    padding: 9px 12px;
    color: var(--gray-1000);
    background: var(--gray-0);
    border-color: var(--gray-200);
    border-radius: 6px;
    box-shadow: none;

    &:hover {
      border-color: var(--gray-400);
    }

    &:focus,
    &:focus-within {
      border-color: var(--main-color);
      box-shadow: 0 0 0 2px color-mix(in srgb, var(--main-color) 12%, transparent);
    }
  }

  :deep(.ant-input-affix-wrapper .ant-input) {
    min-height: 0;
    padding: 0;
    background: transparent;
  }

  :deep(.ant-input-prefix) {
    margin-right: 10px;
    color: var(--gray-400);
  }

  :deep(.ant-btn) {
    height: 46px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 0;
    box-shadow: none;
  }

  :deep(.ant-btn-primary) {
    color: var(--main-0);
    background: var(--gray-900);
    border-color: var(--gray-900);

    &:hover:not(:disabled) {
      background: var(--gray-700);
      border-color: var(--gray-700);
    }

    &:focus-visible {
      outline: 2px solid var(--main-300);
      outline-offset: 2px;
    }
  }
}

.login-form.login-form--init :deep(.ant-form-item) {
  margin-bottom: 16px;
}

.third-party-login {
  margin-top: 22px;

  .divider {
    display: flex;
    align-items: center;
    gap: 14px;
    margin: 24px 0 18px;
    color: var(--gray-400);
    font-size: 11px;

    &::before,
    &::after {
      position: static;
      flex: 1;
      width: auto;
      background: var(--gray-150);
    }

    span {
      padding: 0;
      background: transparent;
      color: inherit;
      font-size: inherit;
    }
  }

  .login-icons :deep(.ant-btn) {
    height: 46px;
    border-color: var(--gray-200);
    border-radius: 6px;
    color: var(--gray-700);
    background: var(--gray-0);
    box-shadow: none;

    &:hover {
      border-color: var(--gray-400);
      color: var(--gray-1000);
      background: var(--gray-25);
    }

    .anticon,
    svg {
      color: var(--gray-500);
    }
  }
}

.agreement-row {
  color: var(--gray-500);
  font-size: 12px;
}

.agreement-link {
  color: var(--gray-800);
  text-underline-offset: 3px;
}

.error-message {
  margin-top: 10px;
  padding: 12px 14px;
  text-align: left;
  border-radius: 6px;
}

.page-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 61px;
  padding: 0 40px;
  border-top: 1px solid var(--gray-150);
  background: var(--gray-10);
}

.footer-links {
  margin: 0;

  a {
    color: var(--gray-600);
    font-size: 11px;
  }
}

.copyright {
  color: var(--gray-400);
  font-size: 10px;
}

.server-status-alert {
  position: fixed;
  padding: 10px 24px;
  background: var(--color-error-700);

  .alert-content {
    max-width: 1440px;
  }
}

@media (max-width: 980px) {
  .login-card {
    grid-template-columns: minmax(300px, 0.8fr) minmax(400px, 1.2fr);
  }

  .card-side.is-image {
    padding: 40px;
  }

  .image-content h2 {
    font-size: 42px;
  }

  .capability-list {
    display: none;
  }

  .card-side.is-form {
    padding: 60px 48px;
  }
}

@media (max-width: 760px) {
  .login-navbar .navbar-content {
    min-height: 64px;
    padding: 0 18px;
  }

  .login-navbar {
    min-height: 64px;
  }

  .navbar-note,
  .brand-org,
  .brand-separator {
    display: none;
  }

  .login-card {
    display: block;
    min-height: calc(100dvh - 64px - 57px);
    margin: 0;
  }

  .card-side.is-image {
    display: none;
  }

  .card-side.is-form {
    min-height: calc(100dvh - 64px - 57px);
    padding: 48px 22px 56px;
  }

  .form-wrapper {
    width: min(100%, 440px);
  }

  .page-footer {
    min-height: 57px;
    padding: 0 18px;
  }

  .copyright {
    max-width: 240px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}
</style>
