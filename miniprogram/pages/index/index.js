// pages/index/index.js
const api = require('../../utils/api.js')

let taskIdCounter = 0

Page({
  data: {
    // 任务列表
    tasks: [],
    showTaskPanel: false, // 面板显示
    editingTaskIndex: null, // 正在编辑的任务索引
    readyCount: 0,
    statusCount: { idle: 0, submitted: 0, processing: 0, completed: 0, failed: 0 },
    taskForm: { // 表单数据
      productImage: '',
      refImage: '',
      text: '限时特惠 5折起',
      prompt: '白色背景，产品居中，专业摄影'
    }
  },

  onLoad() {
    console.log('[Index] onLoad called')
    const token = wx.getStorageSync('token')
    console.log('[Index] Token from storage:', token)
    console.log('[Index] Token check:', token ? 'found' : 'missing')
    
    if (!token) {
      console.log('[Index] No token, redirecting to login')
      wx.showToast({ title: '未登录，跳转登录页', icon: 'none' })
      wx.reLaunch({ url: '/pages/login/login' })
      return
    }
    this.setData({ token })
    console.log('[Index] Token set, loading tasks...')
    this.loadTasks().catch((err) => {
      console.error('loadTasks failed:', err)
      wx.showToast({ title: '任务列表加载失败', icon: 'none' })
    })
  },

  onUnload() {
    // 清除所有轮询定时器
    if (this._pollIntervals && this._pollIntervals.length) {
      this._pollIntervals.forEach(t => clearInterval(t))
      this._pollIntervals = []
    }
  },

  // ================= 任务管理 =================

  // 创建新任务
  onCreateTask() {
    this.setData({
      showTaskPanel: true,
      editingTaskIndex: null,
      taskForm: {
        productImage: '',
        refImage: '',
        text: '',
        prompt: ''
      }
    })
  },

  // 编辑任务
  onEditTask(e) {
    const index = e.currentTarget.dataset.index
    const task = this.data.tasks[index]
    this.setData({
      showTaskPanel: true,
      editingTaskIndex: index,
      taskForm: {
        productImage: task.productImage || '',
        refImage: task.refImage || '',
        text: task.text || '',
        prompt: task.prompt || ''
      }
    })
  },

  // 关闭面板
  closeTaskPanel() {
    this.setData({ showTaskPanel: false, editingTaskIndex: null })
  },

  // 保存任务
  saveTask() {
    const { editingTaskIndex, taskForm } = this.data
    if (!taskForm.productImage || !taskForm.refImage) {
      wx.showToast({ title: '请上传商品图和参考图', icon: 'none' })
      return
    }

    const tasks = [...this.data.tasks]
    if (editingTaskIndex !== null) {
      // 编辑模式
      tasks[editingTaskIndex] = {
        ...tasks[editingTaskIndex],
        productImage: taskForm.productImage,
        refImage: taskForm.refImage,
        text: taskForm.text,
        prompt: taskForm.prompt
      }
    } else {
      // 新增模式
      tasks.push({
        id: `task_${++taskIdCounter}_${Date.now()}`,
        productImage: taskForm.productImage,
        refImage: taskForm.refImage,
        text: taskForm.text,
        prompt: taskForm.prompt,
        status: 'idle',
        statusText: '未提交',
        resultUrls: [],
        backendTaskId: ''
      })
    }

    this._updateTaskCounts(tasks)
    this.setData({
      tasks,
      showTaskPanel: false,
      editingTaskIndex: null,
      taskForm: { productImage: '', refImage: '', text: '', prompt: '' }
    })
  },

  // 删除任务（调用后端 API）
  onDeleteTask(e) {
    const index = e.currentTarget.dataset.index
    const task = this.data.tasks[index]
    if (!task) return

    wx.showModal({
      title: '确认删除',
      content: '确定删除这个任务吗？',
      confirmColor: '#ff4d4f',
      success: async (res) => {
        if (res.confirm) {
          try {
            // 如果任务已提交（有后端ID），先调用删除接口
            if (task.backendTaskId && this.data.token) {
              await api.deleteTask(task.backendTaskId, this.data.token)
            }
            // 本地移除
            const tasks = [...this.data.tasks]
            tasks.splice(index, 1)
            this._updateTaskCounts(tasks)
            this.setData({ tasks })
            wx.showToast({ title: '已删除', icon: 'success' })
          } catch (err) {
            console.error('Delete failed:', err)
            wx.showToast({ title: '删除失败', icon: 'none' })
          }
        }
      }
    })
  },

  // ================= 图片选择 =================

  // 选择图片入口（可指定 sourceType）
  chooseImage(sourceType, callback) {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: sourceType,
      sizeType: ['original'],
      success: (res) => {
        callback(res.tempFiles[0].tempFilePath)
      },
      fail: (err) => {
        if (err.errMsg && (err.errMsg.includes('auth deny') || err.errMsg.includes('cancel'))) {
          wx.showModal({ title: '需要权限', content: '请允许访问相册/相机', confirmText: '去设置', success: (r) => { if (r.confirm) wx.openSetting() } })
        }
      }
    })
  },

  onSelectImage(e) {
    const target = e.currentTarget.dataset.target
    const source = e.currentTarget.dataset.source
    const sourceType = source === 'camera' ? ['camera'] : ['album']
    this.chooseImage(sourceType, (path) => {
      const field = target === 'product' ? 'productImage' : 'refImage'
      this.setData({ [`taskForm.${field}`]: path })
    })
  },

  showImagePicker(callback) {
    wx.showActionSheet({
      itemList: ['拍照', '从相册选择'],
      success: (res) => {
        if (res.tapIndex === 0) {
          this.chooseImage(['camera'], callback)
        } else {
          this.chooseImage(['album'], callback)
        }
      }
    })
  },

  // 商品图操作
  onChangeProductImage() {
    this._showReplacePicker('product')
  },
  onRemoveProductImage() {
    this.setData({ 'taskForm.productImage': '' })
  },

  // 参考图操作
  onChangeRefImage() {
    this._showReplacePicker('ref')
  },

  _showReplacePicker(target) {
    wx.showActionSheet({
      itemList: ['拍照', '从相册选择'],
      success: (res) => {
        const sourceType = res.tapIndex === 0 ? ['camera'] : ['album']
        this.chooseImage(sourceType, (path) => {
          const field = target === 'product' ? 'productImage' : 'refImage'
          this.setData({ [`taskForm.${field}`]: path })
        })
      }
    })
  },
  onRemoveRefImage() {
    this.setData({ 'taskForm.refImage': '' })
  },

  // ================= 表单输入 =================
  onTaskTextInput(e) {
    this.setData({ 'taskForm.text': e.detail.value })
  },
  onTaskPromptInput(e) {
    this.setData({ 'taskForm.prompt': e.detail.value })
  },

  // ================= 提交任务 =================

  // 提交单个任务
  onTaskSubmit(e) {
    const index = e.currentTarget.dataset.index
    this._submitSingleTask(index)
  },

  // 全部提交
  onBatchSubmit() {
    const tasks = this.data.tasks.filter(t => t.status === 'idle')
    if (tasks.length === 0) {
      wx.showToast({ title: '没有可提交的任务', icon: 'none' })
      return
    }
    wx.showModal({
      title: '确认提交',
      content: `提交 ${tasks.length} 个任务，确定继续？`,
      success: (res) => {
        if (res.confirm) {
          this.data.tasks.forEach((t, i) => {
            if (t.status === 'idle') this._submitSingleTask(i, true)
          })
        }
      }
    })
  },

  // 提交单个任务的内部方法
  _submitSingleTask(index, silent = false) {
    const task = this.data.tasks[index]
    if (!task || task.status !== 'idle') return

    this._uploadAndSubmitTask(index, task).catch(err => {
      console.error('Task submit failed:', err)
      const tasks = [...this.data.tasks]
      tasks[index].status = 'failed'
      tasks[index].statusText = '失败'
      this.setData({ tasks })
      if (!silent) {
        wx.showToast({ title: '提交失败', icon: 'none' })
      }
    })
  },

  // 上传并生成
  async _uploadAndSubmitTask(index, task) {
    const token = this.data.token
    if (!token) {
      wx.showToast({ title: '请先登录', icon: 'none' })
      return
    }

    const tasks = [...this.data.tasks]
    tasks[index].status = 'submitted'
    tasks[index].statusText = '已提交'
    this._updateTaskCounts(tasks)
    this.setData({ tasks })

    try {
      // 上传商品图
      const productFileId = await this._uploadFile(task.productImage, token)
      // 上传参考图
      const refFileId = await this._uploadFile(task.refImage, token)

      tasks[index].status = 'processing'
      tasks[index].statusText = '生成中'
      this._updateTaskCounts(tasks)
      this.setData({ tasks })

      // 构建 mapping（prompt 由后端组装，前端只传用户输入）
      const mapping = {
        0: {
          refs: [0],
          text: task.text || '',
          prompt: task.prompt || ''
        }
      }

      // 调用生成接口
      const resp = await api.createTask({
        product_images: [productFileId],
        reference_images: [refFileId],
        mapping,
        prompt: task.prompt || ''
      }, token)

      const backendTaskId = resp.task_id || resp.id
      tasks[index].backendTaskId = backendTaskId
      this._updateTaskCounts(tasks)
      this.setData({ tasks })

      // 开始轮询
      this._pollTask(index, backendTaskId, token)
    } catch (err) {
      tasks[index].status = 'failed'
      tasks[index].statusText = '失败: ' + (err.message || '未知错误')
      this._updateTaskCounts(tasks)
      this.setData({ tasks })
      throw err
    }
  },

  // 上传文件
  _uploadFile(filePath, token) {
    return new Promise((resolve, reject) => {
      wx.uploadFile({
        url: `${api.BASE_URL}/api/upload`,
        filePath,
        name: 'file',
        header: { Authorization: `Bearer ${token}` },
        success: (res) => {
          if (res.statusCode === 200) {
            const data = JSON.parse(res.data)
            resolve(data.file_id)
          } else {
            reject(new Error(`上传失败: ${res.statusCode}`))
          }
        },
        fail: reject
      })
    })
  },

  // 轮询任务状态（每个任务独立定时器，避免泄漏）
  _pollTask(index, taskId, token) {
    const maxAttempts = 300
    let attempts = 0

    if (!this._pollIntervals) this._pollIntervals = []

    const timer = setInterval(async () => {
      attempts++
      try {
        const taskResult = await api.getTask(taskId, token)

        const tasks = [...this.data.tasks]
        if (!tasks[index]) {
          this._clearPollTimer(timer)
          return
        }

        if (taskResult.status === 'completed') {
          this._clearPollTimer(timer)
          tasks[index].status = 'completed'
          tasks[index].statusText = '完成'
          tasks[index].resultUrls = taskResult.result_urls || []
          this._updateTaskCounts(tasks)
          this.setData({ tasks })
        } else if (taskResult.status === 'failed') {
          this._clearPollTimer(timer)
          tasks[index].status = 'failed'
          tasks[index].statusText = taskResult.error || '失败'
          this._updateTaskCounts(tasks)
          this.setData({ tasks })
        }
      } catch (err) {
        if (attempts >= maxAttempts) {
          this._clearPollTimer(timer)
          const tasks = [...this.data.tasks]
          if (tasks[index]) {
            tasks[index].status = 'failed'
            tasks[index].statusText = '请求超时'
            this._updateTaskCounts(tasks)
            this.setData({ tasks })
          }
        }
      }
    }, 3000)

    this._pollIntervals.push(timer)
  },

  // 清理单个轮询定时器
  _clearPollTimer(timer) {
    clearInterval(timer)
    if (this._pollIntervals) {
      this._pollIntervals = this._pollIntervals.filter(t => t !== timer)
    }
  },

  // 更新任务计数
  _updateTaskCounts(tasks) {
    let readyCount = 0
    let statusCounts = { idle: 0, submitted: 0, processing: 0, completed: 0, failed: 0 }
    tasks.forEach(t => {
      if (t.status === 'idle') readyCount++
      statusCounts[t.status] = (statusCounts[t.status] || 0) + 1
    })
    this.setData({ readyCount, statusCount: statusCounts })
  },

  // 加载用户任务列表
  async loadTasks() {
    try {
      const token = this.data.token
      if (!token) {
        console.log('[Index] No token in data, redirecting')
        wx.reLaunch({ url: '/pages/login/login' })
        return
      }
      const resp = await api.getTasks(1, 50, token)
      // 转换数据结构
      const tasks = resp.tasks.map(t => ({
        id: t.id,
        backendTaskId: t.id,
        productImage: '', // 后端返回不包含商品图，需从其他地方获取？
        refImage: '',
        text: '',
        prompt: '',
        status: t.status,
        statusText: this._getStatusText(t.status),
        resultUrls: t.result_urls,
        resultCount: t.result_urls ? t.result_urls.length : 0
      }))
      this.setData({ tasks })
      this._updateTaskCounts(tasks)
    } catch (err) {
      console.error('loadTasks failed:', err)
      // 区分错误类型
      if (err.message === 'UNAUTHORIZED') {
        console.log('[Index] Token expired, re-logging in')
        wx.removeStorageSync('token')
        wx.reLaunch({ url: '/pages/login/login' })
      } else {
        // 其他错误静默失败
        console.warn('[Index] Load tasks failed:', err.message)
      }
    }
  },

  _getStatusText(status) {
    const map = {
      idle: '未提交',
      submitted: '已提交',
      processing: '生成中',
      completed: '完成',
      failed: '失败'
    }
    return map[status] || status
  },

  // 预览图片
  previewImage(e) {
    const url = e.currentTarget.dataset.url
    if (url) wx.previewImage({ current: url, urls: [url] })
  },

  // 保存结果到相册
  onSaveResult(e) {
    const { url } = e.currentTarget.dataset
    if (!url) return

    // 检查相册权限
    wx.getSetting({
      success: (res) => {
        if (!res.authSetting['scope.writePhotosAlbum']) {
          wx.authorize({
            scope: 'scope.writePhotosAlbum',
            success: () => this._downloadAndSave(url),
            fail: () => {
              wx.showModal({
                title: '需要相册权限',
                content: '请允许访问相册以保存图片',
                confirmText: '去设置',
                success: (modalRes) => {
                  if (modalRes.confirm) wx.openSetting()
                }
              })
            }
          })
        } else {
          this._downloadAndSave(url)
        }
      },
      fail: () => wx.showToast({ title: '权限检查失败', icon: 'none' })
    })
  },

  // 下载并保存图片（支持临时 URL 和永久 COS URL）
  _downloadAndSave(url) {
    wx.showLoading({ title: '保存中...' })
    wx.downloadFile({
      url, // 注意：需在小程序后台配置 downloadFile 合法域名
      success: (res) => {
        if (res.statusCode === 200) {
          wx.saveImageToPhotosAlbum({
            filePath: res.tempFilePath,
            success: () => wx.showToast({ title: '已保存', icon: 'success' }),
            fail: (e) => {
              console.error('Save failed:', e)
              wx.showToast({ title: '保存失败', icon: 'none' })
            }
          })
        } else {
          wx.showToast({ title: '下载失败: ' + res.statusCode, icon: 'none' })
        }
      },
      fail: (e) => {
        console.error('Download failed:', e)
        wx.showToast({ title: '下载失败，请检查网络', icon: 'none' })
      },
      complete: () => wx.hideLoading()
    })
  },

  // 遮罩层点击（仅点击遮罩时关闭）
  onOverlayTap(e) {
    if (e.target === e.currentTarget) {
      this.closeTaskPanel()
    }
  }
})
