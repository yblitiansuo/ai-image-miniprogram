// utils/api.js
// API 地址：优先读取小程序全局配置，回退到默认值
const DEFAULT_BASE_URL = 'https://your-api-domain.com'

const app = getApp()
const BASE_URL = (app && app.globalData && app.globalData.apiBaseUrl) || DEFAULT_BASE_URL

const request = (url, method = 'GET', data = {}, token = null) => {
  return new Promise((resolve, reject) => {
    const header = {
      'content-type': 'application/json'
    }
    if (token) {
      header['Authorization'] = `Bearer ${token}`
    }

    wx.request({
      url: BASE_URL + url,
      method,
      data,
      header,
      success: (res) => {
        if (res.statusCode === 200) {
          resolve(res.data)
        } else if (res.statusCode === 401) {
          // 记录错误但不立即弹出，让调用者自己处理
          console.warn('[API] 401 Unauthorized - token 可能已过期')
          reject(new Error('UNAUTHORIZED'))
        } else {
          reject(new Error(res.data?.detail || res.data?.message || '请求失败'))
        }
      },
      fail: (err) => {
        wx.showToast({ title: '网络错误', icon: 'none' })
        reject(err)
      }
    })
  })
}

module.exports = {
  BASE_URL, // 导出 BASE_URL
  // 任务
  createTask(data, token) {
    return request('/api/generate', 'POST', data, token)
  },
  getTask(taskId, token) {
    return request(`/api/task/${taskId}`, 'GET', {}, token)
  },
  getTasks(page = 1, limit = 20, token) {
    return request(`/api/tasks?page=${page}&limit=${limit}`, 'GET', {}, token)
  },
  deleteTask(taskId, token) {
    return request(`/api/task/${taskId}`, 'DELETE', {}, token)
  },

  // 用户
  getUserInfo(token) {
    return request('/user/info', 'GET', {}, token)
  },

  // 支付
  getPackages(token) {
    return request('/pay/packages', 'GET', {}, token)
  },
  createOrder(data, token) {
    return request('/pay/create', 'POST', data, token)
  },
  completePayment(data, token) {
    return request('/pay/complete', 'POST', data, token)
  }
}
