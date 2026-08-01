<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const form = reactive({
  username: 'admin',
  password: '',
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const formRef = ref()

async function handleSubmit() {
  await formRef.value?.validate()
  try {
    await auth.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (error: unknown) {
    const err = error as { response?: { status?: number }; code?: string; message?: string }
    if (!err.response) {
      ElMessage.error('无法连接后端服务，请先启动后端：cd backend && uvicorn app.main:app --reload --port 8000')
    } else if (err.response.status === 403) {
      ElMessage.error('账号已锁定，请 15 分钟后再试')
    } else {
      ElMessage.error('用户名或密码错误')
    }
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card" shadow="hover">
      <div class="login-header">
        <h1>RackDCIM Pro</h1>
        <p>AI Native Data Center Infrastructure Management</p>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="handleSubmit">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="admin" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>
        <el-button type="primary" class="submit-btn" :loading="auth.loading" native-type="submit">
          登录
        </el-button>
      </el-form>
      <p class="hint">默认账号: admin / Admin@12345678</p>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1d1e2c 0%, #2b5876 100%);
  padding: 24px;
}

.login-card {
  width: 100%;
  max-width: 420px;
}

.login-header {
  margin-bottom: 24px;
}

.login-header h1 {
  margin: 0;
  font-size: 24px;
}

.login-header p {
  margin: 8px 0 0;
  color: #909399;
  font-size: 14px;
}

.submit-btn {
  width: 100%;
}

.hint {
  margin: 16px 0 0;
  color: #909399;
  font-size: 12px;
  text-align: center;
}
</style>
