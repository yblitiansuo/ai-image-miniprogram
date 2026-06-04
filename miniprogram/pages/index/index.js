// pages/index/index.js
const api = require('../../utils/api.js')

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
    const token = wx.getStorageSync('token')
    if (!token) {
      wx.showToast({ title: '未登录，跳转登录页', icon: 'none' })
      wx.reLaunch({ url: '/pages/login/login' })
      return
    }
    this.setData({ token })
    this.loadTasks().catch((err) => {
      console.error('loadTasks failed:', err)
      wx.showToast({ title: '任务列表加载失败', icon: 'none' })
    })
  },

  onUnload() {
    // 清除所有轮询定时器
    if (this._pollTimerMap) {
      Object.values(this._pollTimerMap).forEach(t => clearTimeout(t))
      this._pollTimerMap = {}
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
        id: `task_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
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

  // 商品图操作
  showProductPicker() {
    this._showReplacePicker('product')
  },
  onRemoveProductImage() {
    this.setData({ 'taskForm.productImage': '' })
  },

  // 参考图操作
  showRefPicker() {
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

  // 全部提交（串行执行，避免并发上传过多）
  onBatchSubmit() {
    const idleTaskIds = []
    this.data.tasks.forEach((t) => { if (t.status === 'idle') idleTaskIds.push(t.id) })
    if (idleTaskIds.length === 0) {
      wx.showToast({ title: '没有可提交的任务', icon: 'none' })
      return
    }
    wx.showModal({
      title: '确认提交',
      content: `提交 ${idleTaskIds.length} 个任务，确定继续？`,
      success: (res) => {
        if (res.confirm) {
          let pos = 0
          const submitNext = () => {
            if (pos >= idleTaskIds.length) return
            const taskId = idleTaskIds[pos++]
            const idx = this.data.tasks.findIndex(t => t.id === taskId)
            if (idx === -1) { submitNext(); return }
            this._uploadAndSubmitTask(idx, this.data.tasks[idx])
              .then(() => submitNext())
              .catch(() => submitNext())
          }
          // 同时启动 2 个并发
          submitNext()
          if (idleTaskIds.length > 1) submitNext()
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
      const msg = (err.message || '')
      if (msg.includes('402') || msg.includes('配额')) {
        tasks[index].statusText = '配额不足'
      } else if (msg.includes('429') || msg.includes('并发')) {
        tasks[index].statusText = '请稍后再试'
      } else if (msg.includes('上传')) {
        tasks[index].statusText = '上传失败'
      } else {
        tasks[index].statusText = '提交失败'
      }
      this._updateTaskCounts(tasks)
      this.setData({ tasks })
      if (!silent) {
        wx.showToast({ title: tasks[index].statusText, icon: 'none' })
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
      const msg = (err.message || '')
      if (msg.includes('402') || msg.includes('配额')) {
        tasks[index].statusText = '配额不足'
      } else if (msg.includes('429') || msg.includes('并发')) {
        tasks[index].statusText = '请稍后再试'
      } else if (msg.includes('上传')) {
        tasks[index].statusText = '上传失败'
      } else {
        tasks[index].statusText = '提交失败'
      }
      this._updateTaskCounts(tasks)
      this.setData({ tasks })
      throw err
    }
  },

  // 上传文件
  _uploadFile(filePath, token) {
    return new Promise((resolve, reject) => {
      let done = false
      const finish = (fn, val) => {
        if (done) return
        done = true
        fn(val)
      }
      const uploadTask = wx.uploadFile({
        url: `${api.BASE_URL}/api/upload`,
        filePath,
        name: 'file',
        timeout: 30000,
        header: { Authorization: `Bearer ${token}` },
        success: (res) => {
          if (res.statusCode === 200) {
            try {
              const data = JSON.parse(res.data)
              finish(resolve, data.file_id)
            } catch (e) {
              finish(reject, new Error('服务器返回数据格式错误'))
            }
          } else {
            finish(reject, new Error(`上传失败: ${res.statusCode}`))
          }
        },
        fail: (err) => {
          finish(reject, new Error(err.errMsg || '上传失败'))
        }
      })
      // 超时兜底（仅在 wx.uploadFile 的 timeout 未生效时触发）
      setTimeout(() => {
        if (!done) {
          uploadTask.abort()
          finish(reject, new Error('上传超时'))
        }
      }, 35000)
    })
  },

  // 轮询任务状态（指数退避：3s → 5s → 8s → 12s → 15s 封顶）
  _pollTask(index, taskId, token) {
    const maxDuration = 15 * 60 * 1000 // 最长 15 分钟
    const startTime = Date.now()
    let interval = 3000
    let consecutiveErrors = 0
    let currentTimer = null

    if (!this._pollTimerMap) this._pollTimerMap = {}

    const poll = async () => {
      if (!this.data.tasks[index]) { return }
      if (Date.now() - startTime > maxDuration) {
        const tasks = [...this.data.tasks]
        if (tasks[index]) {
          tasks[index].status = 'failed'
          tasks[index].statusText = '生成超时'
          this._updateTaskCounts(tasks)
          this.setData({ tasks })
        }
        delete this._pollTimerMap[taskId]
        return
      }

      try {
        const taskResult = await api.getTask(taskId, token)
        consecutiveErrors = 0

        const tasks = [...this.data.tasks]
        if (!tasks[index]) return

        if (taskResult.status === 'completed') {
          tasks[index].status = 'completed'
          tasks[index].statusText = '完成'
          tasks[index].resultUrls = taskResult.result_urls || []
          this._updateTaskCounts(tasks)
          this.setData({ tasks })
          delete this._pollTimerMap[taskId]
          return
        } else if (taskResult.status === 'failed') {
          tasks[index].status = 'failed'
          tasks[index].statusText = taskResult.error || '失败'
          this._updateTaskCounts(tasks)
          this.setData({ tasks })
          delete this._pollTimerMap[taskId]
          return
        }

        // 未完成，继续轮询，间隔逐步增大
        interval = Math.min(interval + 2000, 15000)
      } catch (err) {
        consecutiveErrors++
        // 连续网络失败超过 5 次才标记超时，避免误判
        if (consecutiveErrors >= 5) {
          const tasks = [...this.data.tasks]
          if (tasks[index]) {
            tasks[index].status = 'failed'
            tasks[index].statusText = '网络异常，请检查网络后重试'
            this._updateTaskCounts(tasks)
            this.setData({ tasks })
          }
          delete this._pollTimerMap[taskId]
          return
        }
        // 网络错误时退避更激进
        interval = Math.min(interval * 1.5, 15000)
      }

      currentTimer = setTimeout(poll, interval)
      this._pollTimerMap[taskId] = currentTimer
    }

    currentTimer = setTimeout(poll, interval)
    this._pollTimerMap[taskId] = currentTimer
  },

  // 按 taskId 清理轮询定时器
  _clearPollTimerForTask(taskId) {
    if (this._pollTimerMap && this._pollTimerMap[taskId]) {
      clearTimeout(this._pollTimerMap[taskId])
      delete this._pollTimerMap[taskId]
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
        productImage: '',
        refImage: '',
        text: t.text || '',
        prompt: t.prompt || '',
        status: t.status,
        statusText: this._getStatusText(t.status),
        resultUrls: t.result_urls,
        resultCount: t.result_urls ? t.result_urls.length : 0,
        createTime: t.created_at || ''
      }))
      this.setData({ tasks })
      this._updateTaskCounts(tasks)
    } catch (err) {
      console.error('loadTasks failed:', err)
      if (err.message === 'UNAUTHORIZED') {
        console.log('[Index] Token expired, re-logging in')
        wx.removeStorageSync('token')
        wx.reLaunch({ url: '/pages/login/login' })
      } else {
        wx.showToast({ title: '任务列表加载失败，请下拉刷新', icon: 'none' })
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

  // 预览图片（支持左右滑动浏览所有结果图）
  previewImage(e) {
    const url = e.currentTarget.dataset.url
    const urls = e.currentTarget.dataset.urls
    if (url) {
      wx.previewImage({ current: url, urls: urls || [url] })
    }
  },

  // 保存结果到相册（支持单张 data-url 和批量 data-urls）
  onSaveResult(e) {
    const { url, urls } = e.currentTarget.dataset
    const targetUrls = urls || (url ? [url] : [])
    if (targetUrls.length === 0) return

    const doSave = () => {
      if (targetUrls.length === 1) {
        this._downloadAndSave(targetUrls[0])
      } else {
        this._downloadAndSaveAll(targetUrls)
      }
    }

    wx.getSetting({
      success: (res) => {
        if (!res.authSetting['scope.writePhotosAlbum']) {
          wx.authorize({
            scope: 'scope.writePhotosAlbum',
            success: doSave,
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
          doSave()
        }
      },
      fail: () => wx.showToast({ title: '权限检查失败', icon: 'none' })
    })
  },

  // 下载并保存单张图片（带超时保护）
  _downloadAndSave(url) {
    wx.showLoading({ title: '保存中...' })
    let done = false
    const finish = (msg, icon) => {
      if (done) return
      done = true
      clearTimeout(timer)
      wx.hideLoading()
      wx.showToast({ title: msg, icon: icon || 'none' })
    }

    const task = wx.downloadFile({
      url,
      success: (res) => {
        if (res.statusCode === 200) {
          wx.saveImageToPhotosAlbum({
            filePath: res.tempFilePath,
            success: () => finish('已保存', 'success'),
            fail: (e) => { console.error('Save failed:', e); finish('保存失败') }
          })
        } else {
          finish('下载失败: ' + res.statusCode)
        }
      },
      fail: (e) => { console.error('Download failed:', e); finish('下载失败，请检查网络') }
    })
    // 30秒超时兜底
    const timer = setTimeout(() => { if (!done) { task.abort(); finish('下载超时') } }, 30000)
  },

  // 批量保存所有结果图（串行，简单可靠）
  _downloadAndSaveAll(urls) {
    wx.showLoading({ title: '保存中...' })
    let saved = 0
    let failed = 0
    const total = urls.length
    let idx = 0

    const finish = () => {
      wx.hideLoading()
      if (failed > 0) {
        wx.showToast({ title: `已保存${saved}张，${failed}张失败`, icon: 'none' })
      } else {
        wx.showToast({ title: `全部${total}张已保存`, icon: 'success' })
      }
    }

    const next = () => {
      if (idx >= total) { finish(); return }
      const url = urls[idx++]
      wx.showLoading({ title: `保存中 ${idx}/${total}` })

      let done = false
      const onDone = (ok) => {
        if (done) return
        done = true
        clearTimeout(timer)
        if (ok) saved++; else failed++
        next()
      }

      const task = wx.downloadFile({
        url,
        success: (res) => {
          if (res.statusCode === 200) {
            wx.saveImageToPhotosAlbum({
              filePath: res.tempFilePath,
              success: () => onDone(true),
              fail: () => onDone(false)
            })
          } else {
            onDone(false)
          }
        },
        fail: () => onDone(false)
      })
      // 30秒超时
      const timer = setTimeout(() => { if (!done) { task.abort(); onDone(false) } }, 30000)
    }

    next()
  },

  // 遮罩层点击（仅点击遮罩时关闭）
  onOverlayTap(e) {
    if (e.target === e.currentTarget) {
      this.closeTaskPanel()
    }
  }
})
