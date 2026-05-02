// app.js
// 配置：true=模拟登录（本地测试），false=真实微信登录（上线）
const USE_MOCK_LOGIN = true  // 临时启用 Mock 模式测试 UI

App({
  globalData: {
    token: null,
    userId: null,
    apiKey: '',
    theme: 'light',
    user: null,
    useMockLogin: USE_MOCK_LOGIN,
    // 备案期间使用 SSH 隧道：ssh -L 9999:127.0.0.1:9999 ubuntu@YOUR_SERVER_IP
    // 备案通过后改为 'https://your-api-domain.com'
    apiBaseUrl: 'http://127.0.0.1:9999'
  },

  onLaunch() {
    // 读取本地缓存
    const token = wx.getStorageSync('token')
    const userId = wx.getStorageSync('userId')
    const apiKey = wx.getStorageSync('apiKey')
    const theme = wx.getStorageSync('theme') || 'light'
    const mockUser = wx.getStorageSync('mock_user')

    if (token) this.globalData.token = token
    if (userId) this.globalData.userId = userId
    if (apiKey) this.globalData.apiKey = apiKey
    if (mockUser) this.globalData.user = mockUser
    this.globalData.theme = theme

    if (!USE_MOCK_LOGIN) {
      this.checkRealLogin()
    }
  },

  // 检查真实登录
  checkRealLogin() {
    const token = wx.getStorageSync('token')
    if (token) {
      this.globalData.token = token
      this.globalData.userId = wx.getStorageSync('userId')
      console.log('[App] 真实登录已恢复')
    }
  },

  // 获取当前用户
  getCurrentUser() {
    return this.globalData.user
  },

  // 获取 Token
  getToken() {
    return this.globalData.token || wx.getStorageSync('token') || null
  },

  // 检查是否已登录
  isLoggedIn() {
    return !!(this.globalData.token || wx.getStorageSync('token'))
  },

  // 退出登录
  logout() {
    wx.removeStorageSync('token')
    wx.removeStorageSync('userId')
    wx.removeStorageSync('apiKey')
    wx.removeStorageSync('mock_user')
    this.globalData.token = null
    this.globalData.userId = null
    this.globalData.user = null
    wx.showToast({ title: '已退出登录', icon: 'none' })
  }
})
