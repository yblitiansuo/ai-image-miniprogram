// pages/user/user.js
const app = getApp()
const api = require('../../utils/api')

Page({
  data: {
    token: '',
    userId: '',
    theme: 'light',
    quota: 0,
    totalGenerated: 0,
    runningTasks: 0,
    createdAt: '',
    tasks: [],
    statusText: {
      pending: '排队中',
      processing: '生成中',
      completed: '已完成',
      failed: '失败'
    }
  },

  onLoad() {
    this.setData({
      token: wx.getStorageSync('token') || '',
      userId: wx.getStorageSync('userId') || '',
      theme: app.globalData.theme || 'light'
    })
    this.loadUserInfo()
    this.loadTasks()
  },

  onShow() {
    if (!this.data.token) {
      wx.redirectTo({ url: '/pages/login/login' })
    } else {
      this.loadUserInfo()
      this.loadTasks()
    }
  },

  async loadUserInfo() {
    try {
      const info = await api.getUserInfo(this.data.token)
      this.setData({
        quota: info.quota,
        totalGenerated: info.total_generated,
        runningTasks: info.running_tasks,
        createdAt: this.formatDate(info.created_at)
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
    }
  },

  formatDate(isoStr) {
    if (!isoStr) return ''
    const date = new Date(isoStr)
    return `${date.getFullYear()}-${date.getMonth()+1}-${date.getDate()}`
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
          wx.removeStorageSync('token')
          wx.removeStorageSync('userId')
          app.globalData.token = null
          app.globalData.userId = null
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
