// pages/user/user.js
const app = getApp()
const api = require('../../utils/api')

Page({
  data: {
    token: '',
    userId: '',
    quota: 0,
    totalGenerated: 0,
    runningTasks: 0,
    createdAt: '',
    firstLetter: '',
    quotaPct: 0,
    tasks: [],
    statusText: {
      pending: '排队中',
      processing: '生成中',
      completed: '已完成',
      failed: '失败'
    }
  },

  onLoad() {
    const userId = wx.getStorageSync('userId') || ''
    this.setData({
      token: wx.getStorageSync('token') || '',
      userId,
      firstLetter: userId ? userId.charAt(0).toUpperCase() : '?'
    })
    this.loadUserInfo()
    this.loadTasks()
    this._loaded = true
  },

  onShow() {
    if (!this.data.token) {
      wx.redirectTo({ url: '/pages/login/login' })
    } else if (this._loaded) {
      // 非首次加载时才刷新，避免 onLoad+onShow 重复请求
      this.loadUserInfo()
      this.loadTasks()
    }
  },

  async loadUserInfo() {
    try {
      const info = await api.getUserInfo(this.data.token)
      const total = info.total_generated + info.quota
      const pct = total > 0 ? Math.round((info.total_generated / total) * 100) : 0
      this.setData({
        quota: info.quota,
        totalGenerated: info.total_generated,
        runningTasks: info.running_tasks,
        createdAt: this.formatDate(info.created_at),
        quotaPct: pct
      })
    } catch (err) {
      console.error('Get user info failed:', err)
    }
  },

  async loadTasks() {
    try {
      const res = await api.getTasks(1, 20, this.data.token)
      this.setData({ tasks: res.tasks || [] })
    } catch (err) {
      console.error('Get tasks failed:', err)
      wx.showToast({ title: '任务列表加载失败', icon: 'none' })
    }
  },

  formatDate(isoStr) {
    if (!isoStr) return ''
    const date = new Date(isoStr)
    const m = String(date.getMonth() + 1).padStart(2, '0')
    const d = String(date.getDate()).padStart(2, '0')
    return `${date.getFullYear()}-${m}-${d}`
  },

  goToPurchase() {
    wx.navigateTo({ url: '/pages/purchase/purchase' })
  },

  onLogout() {
    wx.showModal({
      title: '退出登录',
      content: '确定要退出吗？',
      success: (res) => {
        if (res.confirm) {
          app.logout()
          wx.redirectTo({ url: '/pages/login/login' })
        }
      }
    })
  },

  previewResult(e) {
    const { urls } = e.currentTarget.dataset
    if (urls && urls.length > 0) {
      wx.previewImage({
        current: urls[0],
        urls
      })
    }
  }
})
