// pages/purchase/purchase.js
const app = getApp()
const api = require('../../utils/api')

Page({
  data: {
    token: '',
    theme: 'light',
    packages: [],
    selectedPackage: null
  },

  onLoad() {
    this.setData({
      token: wx.getStorageSync('token') || '',
      theme: app.globalData.theme || 'light'
    })
    this.loadPackages()
  },

  async loadPackages() {
    try {
      const res = await api.getPackages(this.data.token)
      const available = res.packages.filter(p => p.quota !== -1)
      this.setData({ packages: available })
      if (available.length > 0) {
        this.setData({ selectedPackage: available[0].id })
      }
    } catch (err) {
      wx.showToast({ title: '加载套餐失败', icon: 'none' })
    }
  },

  onSelectPackage(e) {
    const id = e.currentTarget.dataset.id
    this.setData({ selectedPackage: id })
  },

  onPurchase() {
    wx.showModal({
      title: '功能建设中',
      content: '支付功能正在对接微信支付，敬请期待',
      showCancel: false
    })
  }
})
