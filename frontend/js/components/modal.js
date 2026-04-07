/**
 * 模态框（弹窗）组件
 */

/**
 * 显示确认对话框
 * @param {Object} options
 *   - title: 标题
 *   - message: 消息
 *   - confirmText: 确认按钮文本 (默认: '确认')
 *   - cancelText: 取消按钮文本 (默认: '取消')
 *   - onConfirm: 确认回调
 *   - onCancel: 取消回调
 * @returns {Promise<boolean>} - 返回用户的选择
 */
export function showConfirm(options) {
  return new Promise((resolve) => {
    const {
      title = '确认',
      message = '',
      confirmText = '确认',
      cancelText = '取消',
      onConfirm = null,
      onCancel = null,
    } = options;

    const modal = createModalElement(title, `
      <p class="text-gray-300 mb-6">${escapeHtml(message)}</p>
    `, [
      {
        text: cancelText,
        className: 'btn-secondary',
        onClick: () => {
          closeModal(modal);
          onCancel?.();
          resolve(false);
        }
      },
      {
        text: confirmText,
        className: 'btn-primary',
        onClick: () => {
          closeModal(modal);
          onConfirm?.();
          resolve(true);
        }
      }
    ]);

    showModal(modal);
  });
}

/**
 * 显示自定义表单对话框
 * @param {Object} options
 *   - title: 标题
 *   - fields: 表单字段数组
 *     - name: 字段名
 *     - label: 标签
 *     - type: 'text' | 'number' | 'select' | 'checkbox' (默认: 'text')
 *     - required: 是否必填
 *     - options: (select 类型) 选项数组 [{ label, value }]
 *     - value: 初始值
 *   - onSubmit: 提交回调 (values: Object)
 *   - onCancel: 取消回调
 * @returns {Promise<Object>} - 返回表单数据
 */
export function showFormModal(options) {
  return new Promise((resolve) => {
    const {
      title = '表单',
      fields = [],
      onSubmit = null,
      onCancel = null,
    } = options;

    let formHtml = '<form class="space-y-4">';

    fields.forEach(field => {
      const { name, label, type = 'text', required = false, options: fieldOptions = [], value = '' } = field;

      if (type === 'select') {
        formHtml += `
          <div>
            <label class="block text-sm font-medium mb-2">${escapeHtml(label)}</label>
            <select name="${name}" class="w-full" ${required ? 'required' : ''}>
              <option value="">-- 选择 --</option>
              ${fieldOptions.map(opt => `<option value="${opt.value}" ${opt.value === value ? 'selected' : ''}>${escapeHtml(opt.label)}</option>`).join('')}
            </select>
          </div>
        `;
      } else if (type === 'checkbox') {
        formHtml += `
          <div class="flex items-center">
            <input type="checkbox" name="${name}" id="${name}" ${value ? 'checked' : ''}>
            <label for="${name}" class="ml-2 text-sm">${escapeHtml(label)}</label>
          </div>
        `;
      } else if (type === 'textarea') {
        formHtml += `
          <div>
            <label class="block text-sm font-medium mb-2">${escapeHtml(label)}</label>
            <textarea name="${name}" class="w-full h-24" ${required ? 'required' : ''}>${escapeHtml(value)}</textarea>
          </div>
        `;
      } else {
        formHtml += `
          <div>
            <label class="block text-sm font-medium mb-2">${escapeHtml(label)}</label>
            <input type="${type}" name="${name}" class="w-full" value="${escapeHtml(value)}" ${required ? 'required' : ''}>
          </div>
        `;
      }
    });

    formHtml += '</form>';

    const modal = createModalElement(title, formHtml, [
      {
        text: '取消',
        className: 'btn-secondary',
        onClick: () => {
          closeModal(modal);
          onCancel?.();
          resolve(null);
        }
      },
      {
        text: '提交',
        className: 'btn-primary',
        onClick: () => {
          const form = modal.querySelector('form');
          if (!form.checkValidity()) {
            form.reportValidity();
            return;
          }

          const formData = new FormData(form);
          const values = {};
          formData.forEach((value, key) => {
            const field = fields.find(f => f.name === key);
            if (field?.type === 'checkbox') {
              values[key] = formData.get(key) !== null;
            } else {
              values[key] = value;
            }
          });

          closeModal(modal);
          onSubmit?.(values);
          resolve(values);
        }
      }
    ]);

    showModal(modal);
  });
}

/**
 * 显示提示框
 * @param {Object} options
 *   - title: 标题
 *   - message: 消息
 * @returns {Promise<void>}
 */
export function showAlert(options) {
  return new Promise((resolve) => {
    const { title = '提示', message = '' } = options;

    const modal = createModalElement(title, `
      <p class="text-gray-300">${escapeHtml(message)}</p>
    `, [
      {
        text: '确定',
        className: 'btn-primary',
        onClick: () => {
          closeModal(modal);
          resolve();
        }
      }
    ]);

    showModal(modal);
  });
}

/**
 * 显示加载框 (不自动关闭)
 * @param {string} message
 * @returns {Function} - 返回关闭函数
 */
export function showLoading(message = '加载中...') {
  const modal = createModalElement('请稍候', `
    <div class="flex flex-col items-center gap-4">
      <div class="animate-spin">
        <svg class="w-8 h-8 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"></path>
        </svg>
      </div>
      <p class="text-gray-300">${escapeHtml(message)}</p>
    </div>
  `, [], { dismissible: false });

  showModal(modal);

  return () => closeModal(modal);
}

// ============================================
// 内部函数
// ============================================

function createModalElement(title, content, buttons = [], options = {}) {
  const { dismissible = true } = options;

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';

  const modalContent = document.createElement('div');
  modalContent.className = 'modal-content';

  // 标题
  const header = document.createElement('div');
  header.className = 'modal-header';
  header.innerHTML = `
    <h2 class="modal-title">${escapeHtml(title)}</h2>
    ${dismissible ? '<button class="modal-close">&times;</button>' : ''}
  `;
  if (dismissible) {
    header.querySelector('.modal-close').onclick = () => closeModal(overlay);
  }

  // 内容
  const body = document.createElement('div');
  body.className = 'modal-body';
  body.innerHTML = content;

  // 底部按钮
  const footer = document.createElement('div');
  footer.className = 'modal-footer';
  buttons.forEach(btn => {
    const button = document.createElement('button');
    button.textContent = btn.text;
    button.className = btn.className;
    button.onclick = btn.onClick;
    footer.appendChild(button);
  });

  modalContent.appendChild(header);
  modalContent.appendChild(body);
  if (buttons.length > 0) {
    modalContent.appendChild(footer);
  }

  overlay.appendChild(modalContent);

  // 点击背景关闭
  if (dismissible) {
    overlay.onclick = (e) => {
      if (e.target === overlay) {
        closeModal(overlay);
      }
    };
  }

  return overlay;
}

function showModal(modal) {
  const container = document.getElementById('modal-container');
  if (container) {
    container.appendChild(modal);
  }
}

function closeModal(modal) {
  modal.style.opacity = '0';
  setTimeout(() => {
    modal.remove();
  }, 200);
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
