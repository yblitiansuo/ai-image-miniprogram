// pages/login/login.js
const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    isLoggingIn: false,
    loading: false
  },

  onLoad() {
    // 如果已经登录，直接跳转到首页(tabBar 页面要用 switchTab)
    if (app.isLoggedIn()) {
      wx.switchTab({
        url: '/pages/index/index'
      })
    }
  },

  onShow() {
    // 页面显示时，检查是否需要登录
    if (app.isLoggedIn()) {
      wx.switchTab({
        url: '/pages/index/index'
      })
    }
  },

  /**
   * 登录入口：本地测试走 mock，上线走微信授权
   */
  handleMockLogin() {
    this.setData({ isLoggingIn: true })

    if (app.globalData.useMockLogin) {
      // 先调用后端获取真实 token
      wx.request({
        url: api.BASE_URL + '/auth/login',
        method: 'POST',
        data: { code: 'mock_test_code' },
        header: { 'content-type': 'application/json' },
        success: (res) => {
          if (res.statusCode === 200) {
            const token = res.data.token
            const userId = res.data.user_id

            console.log('[Login] Response:', res)
            console.log('[Login] Token:', token)
            console.log('[Login] UserId:', userId)

            // 保存 token 到本地存储
            wx.setStorageSync('token', token)
            wx.setStorageSync('userId', userId)

            // 验证保存结果
            const savedToken = wx.getStorageSync('token')
            console.log('[Login] Saved token:', savedToken)

            // 更新全局状态
            app.globalData.token = token
            app.globalData.userId = userId

            console.log('[Login] Global token:', app.globalData.token)

            wx.showToast({
              title: '登录成功',
              icon: 'success'
            })

            // 延迟跳转，确保状态同步
            setTimeout(() => {
              wx.switchTab({
                url: '/pages/index/index'
              })
            }, 500)
          } else {
            this.setData({ isLoggingIn: false })
            wx.showToast({ title: '登录失败', icon: 'none' })
          }
        },
        fail: (err) => {
          console.error('Login failed:', err)
          this.setData({ isLoggingIn: false })
          wx.showToast({ title: '登录失败', icon: 'none' })
        }
      })
      return
    }

    wx.login({
      success: async (res) => {
        if (!res.code) {
          this.setData({ isLoggingIn: false })
          wx.showToast({ title: '获取登录凭证失败', icon: 'none' })
          return
        }

        try {
          const loginResp = await new Promise((resolve, reject) => {
            wx.request({
              url: api.BASE_URL + '/auth/login',
              method: 'POST',
              data: { code: res.code },
              header: { 'content-type': 'application/json' },
              success: (r) => {
                if (r.statusCode === 200) resolve(r.data)
                else reject(new Error(r.data?.detail || '登录失败'))
              },
              fail: reject
            })
          })

          wx.setStorageSync('token', loginResp.token)
          wx.setStorageSync('userId', loginResp.user_id)
          app.globalData.token = loginResp.token
          app.globalData.userId = loginResp.user_id

          wx.showToast({ title: '登录成功', icon: 'success' })
          setTimeout(() => {
            wx.switchTab({ url: '/pages/index/index' })
          }, 300)
        } catch (err) {
          console.error('Login failed:', err)
          wx.showToast({ title: err.message || '登录失败', icon: 'none' })
        } finally {
          this.setData({ isLoggingIn: false })
        }
      },
      fail: (err) => {
        console.error('wx.login failed:', err)
        this.setData({ isLoggingIn: false })
        wx.showToast({ title: '微信登录失败', icon: 'none' })
      }
    })
  },

  /**
   * 测试用：强制刷新登录状态
   */
  handleForceRefresh() {
    wx.removeStorageSync('mock_user')
    wx.removeStorageSync('token')
    wx.removeStorageSync('userId')
    app.globalData.user = null
    app.globalData.token = null
    app.globalData.userId = null
    wx.showToast({
      title: '已清除登录状态',
      icon: 'none'
    })
  }
})
