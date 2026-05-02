function compareVersion(v1, v2) {
  const v1parts = v1.split('.').map(Number)
  const v2parts = v2.split('.').map(Number)
  const len = Math.max(v1parts.length, v2parts.length)
  for (let i = 0; i < len; i++) {
    const num1 = v1parts[i] || 0
    const num2 = v2parts[i] || 0
    if (num1 > num2) return 1
    if (num1 < num2) return -1
  }
  return 0
}

Page({
  data: {
    src: '',
    type: '',
    imgWidth: 0,
    imgHeight: 0,
    canvasWidth: 0,
    canvasHeight: 0,
    scale: 1,
    rotate: 0,
    cropX: 0,
    cropY: 0,
    cropW: 0,
    cropH: 0,
    aspectRatio: 0,
    cropModes: [
      { label: '自由', value: 0 },
      { label: '1:1', value: 1 },
      { label: '4:3', value: 4/3 },
      { label: '16:9', value: 16/9 }
    ],
    selectedMode: 0,
    sdkVersion: ''
  },

  onLoad(options) {
    const { src, type } = options
    if (!src || !type) {
      wx.showToast({ title: '参数错误', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 1500)
      return
    }
    // 检测基础库版本，需 >= 2.10.0 支持离屏 canvas 裁剪
    const sys = wx.getSystemInfoSync()
    const sdkVersion = sys.SDKVersion
    this.setData({ src, type, sdkVersion })
    this.getImageInfo(src)
  },

  getImageInfo(src) {
    wx.getImageInfo({
      src,
      success: (res) => {
        const { width, height } = res
        const { windowWidth } = wx.getSystemInfoSync()
        const maxW = windowWidth - 32
        const ratio = Math.min(1, maxW / width)
        const canvasW = Math.floor(width * ratio)
        const canvasH = Math.floor(height * ratio)
        this.setData({
          imgWidth: width,
          imgHeight: height,
          canvasWidth: canvasW,
          canvasHeight: canvasH,
          cropX: 0,
          cropY: 0,
          cropW: canvasW,
          cropH: canvasH,
          scale: 1
        })
        this.draw()
      },
      fail: (err) => {
        wx.showToast({ title: '无法加载图片', icon: 'none' })
        setTimeout(() => wx.navigateBack(), 1500)
      }
    })
  },

  draw() {
    const { src, imgWidth, imgHeight, canvasWidth, canvasHeight, scale, rotate, cropX, cropY, cropW, cropH } = this.data
    const ctx = wx.createCanvasContext('editCanvas', this)
    ctx.clearRect(0, 0, canvasWidth, canvasHeight)

    ctx.save()
    const cx = canvasWidth / 2
    const cy = canvasHeight / 2
    ctx.translate(cx, cy)
    ctx.rotate(rotate * Math.PI / 180)
    ctx.scale(scale, scale)
    ctx.translate(-cx, -cy)
    ctx.drawImage(src, 0, 0, imgWidth, imgHeight, 0, 0, canvasWidth, canvasHeight)
    ctx.restore()

    ctx.setFillStyle('rgba(0,0,0,0.6)')
    ctx.fillRect(0, 0, canvasWidth, canvasHeight)

    ctx.save()
    ctx.setGlobalCompositeOperation('destination-out')
    ctx.setFillStyle('rgba(255,255,255,1)')
    ctx.fillRect(cropX, cropY, cropW, cropH)
    ctx.restore()

    ctx.setStrokeStyle('#fff')
    ctx.setLineWidth(2)
    ctx.strokeRect(cropX, cropY, cropW, cropH)

    ctx.draw()
  },

  onTouchStart(e) {
    this.touchStart = e.touches[0]
  },

  onTouchMove(e) {
    const touch = e.touches[0]
    const start = this.touchStart
    const dx = touch.x - start.x
    const dy = touch.y - start.y
    const { cropX, cropY, cropW, cropH, canvasWidth, canvasHeight } = this.data

    let newX = cropX + dx
    let newY = cropY + dy
    newX = Math.max(0, Math.min(newX, canvasWidth - cropW))
    newY = Math.max(0, Math.min(newY, canvasHeight - cropH))

    this.setData({ cropX: newX, cropY: newY })
    this.touchStart = touch
    this.draw()
  },

  onRotate() {
    const rotate = (this.data.rotate + 90) % 360
    const { canvasWidth, canvasHeight, selectedMode } = this.data
    const mode = selectedMode || 0
    let ratio = mode
    if (mode === 0) {
      ratio = canvasWidth / canvasHeight
    }
    const w = Math.min(canvasWidth * 0.8, canvasHeight * 0.8 * ratio)
    const h = w / ratio
    this.setData({
      rotate,
      cropX: (canvasWidth - w) / 2,
      cropY: (canvasHeight - h) / 2,
      cropW: w,
      cropH: h
    }, this.draw)
  },

  onAspectChange(e) {
    const value = parseFloat(e.currentTarget.dataset.value)
    const { canvasWidth, canvasHeight } = this.data
    let ratio = value || (canvasWidth / canvasHeight)
    let maxW = canvasWidth * 0.9
    let maxH = canvasHeight * 0.9
    let newW = maxW
    let newH = newW / ratio
    if (newH > maxH) {
      newH = maxH
      newW = newH * ratio
    }
    const x = (canvasWidth - newW) / 2
    const y = (canvasHeight - newH) / 2
    this.setData({
      selectedMode: value,
      cropX: x,
      cropY: y,
      cropW: newW,
      cropH: newH
    }, this.draw)
  },

  onZoom(e) {
    const { type } = e.currentTarget.dataset
    const { scale, cropW, cropH, cropX, cropY } = this.data
    const factor = type === 'plus' ? 1.1 : 0.9
    let newScale = scale * factor
    newScale = Math.max(0.5, Math.min(3, newScale))
    const newW = cropW * factor
    const newH = cropH * factor
    const dx = (newW - cropW) / 2
    const dy = (newH - cropH) / 2
    this.setData({
      scale: newScale,
      cropW: newW,
      cropH: newH,
      cropX: cropX - dx,
      cropY: cropY - dy
    }, this.draw)
  },

  async onConfirm() {
    if (compareVersion(this.data.sdkVersion, '2.10.0') < 0) {
      wx.showModal({
        title: '版本过低',
        content: '图片编辑功能需要微信基础库 2.10.0 或更高版本，请升级微信',
        showCancel: false
      })
      return
    }
    const { canvasWidth, canvasHeight, cropX, cropY, cropW, cropH, type } = this.data
    wx.showLoading({ title: '处理中...' })
    try {
      const fullCanvas = await new Promise((resolve, reject) => {
        wx.canvasToTempFilePath({
          canvasId: 'editCanvas',
          x: 0,
          y: 0,
          width: canvasWidth,
          height: canvasHeight,
          destWidth: canvasWidth,
          destHeight: canvasHeight,
          quality: 1,
          success: res => resolve(res.tempFilePath),
          fail: err => reject(err)
        }, this)
      })

      const croppedPath = await this.cropImage(fullCanvas, cropX, cropY, cropW, cropH)

      const pages = getCurrentPages()
      const prev = pages[pages.length - 2]
      if (prev && typeof prev.onEditComplete === 'function') {
        prev.onEditComplete(type, croppedPath)
      }
      wx.navigateBack()
    } catch (err) {
      console.error(err)
      wx.showToast({ title: '编辑失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },

  cropImage(fullPath, x, y, w, h) {
    return new Promise((resolve, reject) => {
      const offCanvas = wx.createOffscreenCanvas({ type: '2d' })
      offCanvas.width = Math.floor(w)
      offCanvas.height = Math.floor(h)
      const ctx = offCanvas.getContext('2d')
      const img = offCanvas.createImage()
      img.onload = () => {
        ctx.drawImage(img, x, y, w, h, 0, 0, w, h)
        wx.canvasToTempFilePath({
          canvas: offCanvas,
          success: res => resolve(res.tempFilePath),
          fail: err => reject(err)
        }, this)
      }
      img.onerror = (e) => reject(e)
      img.src = fullPath
    })
  },

  onCancel() {
    wx.navigateBack()
  }
})
