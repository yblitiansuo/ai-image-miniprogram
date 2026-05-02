// pages/purchase/purchase.js
const app = getApp()
const api = require('../../utils/api')

Page({
  data: {
    token: '',
    theme: 'light',
    packages: [],
    selectedPackage: null,
    purchasing: false
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
      // 过滤掉无限套餐（暂不支持）
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

  async onPurchase() {
    if (!this.data.selectedPackage) {
      wx.showToast({ title: '请选择套餐', icon: 'none' })
      return
    }

    this.setData({ purchasing: true })

    try {
      // 1. 创建订单
      const orderRes = await api.createOrder({
        package_id: this.data.selectedPackage
      }, this.data.token)

      const orderId = orderRes.order_id

      // 2. 模拟支付完成（生产环境需调用微信支付）
      await api.completePayment({ order_id: orderId }, this.data.token)

      wx.showModal({
        title: '购买成功',
        content: `已增加 ${orderRes.quota_added} 次配额`,
        showCancel: false,
        success: () => {
          // 返回用户中心
          wx.navigateBack()
        }
      })

    } catch (err) {
      console.error('Purchase error:', err)
      wx.showModal({
        title: '购买失败',
        content: err.message || '网络错误，请重试',
        showCancel: false
      })
    } finally {
      this.setData({ purchasing: false })
    }
  }
})
