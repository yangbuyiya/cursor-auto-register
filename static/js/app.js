// 全局变量
const REFRESH_INTERVAL = 10000; // 10秒
let currentPage = 1;
let totalPages = 1;
let itemsPerPage = 10;
let currentSortField = 'created_at';
let currentSortOrder = 'desc';

// 页面加载完成后执行
$(document).ready(function () {
  // 初始化应用
  initializeApplication();

  // 每60秒检查一次服务状态
  setInterval(checkTaskStatus, 60 * 1000);

  // 绑定遮罩关闭按钮事件 - 使用事件委托确保对动态元素也有效
  $(document).on('click', '.close-overlay', function () {
    hideLoading();
  });

  // 绑定确认删除按钮事件
  $(document).on('click', '#confirmDeleteBtn', function () {
    deleteAccount();
  });
});

// 添加防抖函数实现
function debounce(func, wait = 300) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// 添加节流函数实现
function throttle(func, limit = 300) {
  let inThrottle;
  return function (...args) {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
}

// 应用初始化函数 - 提高代码组织性
function initializeApplication() {
  // 绑定分页事件必须在DOM准备好后立即执行
  bindPaginationEvents();

  // 绑定排序事件
  bindSortEvents();

  // 确保不使用ID排序
  if (currentSortField === 'id') {
    currentSortField = 'created_at';
  }

  // 绑定模态框内按钮事件
  bindModalEvents();

  // 绑定验证码相关事件
  bindVerificationEvents();

  // 为所有模态框绑定全局事件
  setupGlobalModalEvents();

  // 加载配置
  loadConfig();

  // 初始加载数据
  loadAccounts(1, itemsPerPage);

  // 设置定时刷新
  setupTaskRefresh();

  // 绑定所有事件处理函数
  bindEventHandlers();

  // 初始清理背景遮罩，确保页面加载时没有残留
  cleanupModalBackdrops();

  // 在自动刷新指示器中添加最后更新时间显示
  $('.position-fixed.bottom-0.end-0 .d-flex').append(
    '<span class="ms-2">最后更新: <span id="last-update-time">--:--:--</span></span>'
  );

  // 立即更新一次时间，显示页面初始加载时间
  updateLastRefreshTime();
}

// 设置全局模态框事件
function setupGlobalModalEvents() {
  // 为所有模态框的隐藏事件添加背景清理
  $(document).on('hidden.bs.modal', '.modal', function () {
    // 延迟清理背景，避免与Bootstrap的处理冲突
    setTimeout(() => cleanupModalBackdrops(), 150);
  });

  // 处理所有模态框的显示事件，确保不会有多个模态框同时打开
  $(document).on('show.bs.modal', '.modal', function (event) {
    // 如果已经有其他模态框打开，先关闭它们
    const otherModals = $('.modal.show').not(this);
    if (otherModals.length > 0) {
      otherModals.modal('hide');
      // 给予足够时间让其他模态框关闭
      setTimeout(() => cleanupModalBackdrops(), 300);
    }
  });
}

// 事件处理绑定函数 - 将所有事件绑定集中在一起
function bindEventHandlers() {
  // 重新绑定刷新按钮事件，使用防抖处理
  $('#refresh-btn')
    .off('click')
    .on(
      'click',
      debounce(function () {
        fetchAccounts();
      }, 500)
    );

  // 搜索按钮点击事件，使用防抖处理
  $('#search-btn')
    .off('click')
    .on(
      'click',
      debounce(function () {
        filterAccounts();
      }, 300)
    );

  // 搜索框回车事件，使用防抖处理
  $('#search-input')
    .off('keypress')
    .on(
      'keypress',
      debounce(function (e) {
        if (e.which === 13) {
          filterAccounts();
        }
      }, 300)
    );

  // 清除搜索按钮点击事件
  $('#clear-search-btn')
    .off('click')
    .on('click', function () {
      $('#search-input').val('');
      filterAccounts();
    });

  // 开始注册按钮点击事件，使用节流处理避免快速多次点击
  $('#start-registration')
    .off('click')
    .on(
      'click',
      throttle(function () {
        startTaskManually();
      }, 1000)
    );

  // 停止注册按钮点击事件，使用节流处理避免快速多次点击
  $('#stop-registration')
    .off('click')
    .on(
      'click',
      throttle(function () {
        stopTaskManually();
      }, 1000)
    );

  // 自定义邮箱注册按钮点击事件，使用节流处理
  $('#custom-registration')
    .off('click')
    .on(
      'click',
      throttle(function () {
        registerWithCustomEmail();
      }, 1000)
    );

  // 自定义邮箱输入框回车事件
  $('#custom-email')
    .off('keypress')
    .on('keypress', function (e) {
      if (e.which === 13) {
        registerWithCustomEmail();
      }
    });

  // 导出账号按钮点击事件
  $('#export-accounts-btn')
    .off('click')
    .on(
      'click',
      debounce(function () {
        exportAccounts();
      }, 500)
    );

  // 导入账号按钮点击事件
  $('#import-accounts-btn')
    .off('click')
    .on('click', function () {
      $('#import-file-input').click();
    });

  // 重启服务按钮点击事件，使用节流处理
  $('#restart-service-btn')
    .off('click')
    .on(
      'click',
      throttle(function () {
        restartService();
      }, 3000)
    ); // 较长的节流时间防止频繁重启

  // 重置机器ID按钮点击事件，使用节流处理
  $('#reset-machine-btn')
    .off('click')
    .on(
      'click',
      throttle(function () {
        resetMachineId();
      }, 3000)
    ); // 较长的节流时间防止频繁重置

  // 编辑配置按钮点击事件
  $('#edit-config-btn')
    .off('click')
    .on('click', function (e) {
      // 阻止事件冒泡，防止可能的表单提交
      e.preventDefault();
      e.stopPropagation();
      enableConfigForm(true);
    });

  // 取消配置编辑按钮点击事件
  $('#cancel-config-btn')
    .off('click')
    .on('click', function (e) {
      // 阻止事件冒泡，防止可能的表单提交
      e.preventDefault();
      e.stopPropagation();
      enableConfigForm(false);
      loadConfig(); // 重新加载原始配置
    });

  // 保存配置表单提交事件，使用节流处理
  $('#config-form')
    .off('submit')
    .on(
      'submit',
      throttle(function (e) {
        e.preventDefault();
        saveConfig();
      }, 1000)
    );

  // 每页显示数量下拉框变化事件，使用防抖处理
  $('#per-page')
    .off('change')
    .on(
      'change',
      debounce(function () {
        itemsPerPage = parseInt($(this).val());
        currentPage = 1; // 重置到第一页
        renderAccountsTable();
      }, 300)
    );

  // 导入文件选择变化事件
  $('#import-file-input')
    .off('change')
    .on('change', function (e) {
      const file = e.target.files[0];
      if (file) {
        importAccounts(file);
      }
    });

  // 确认导入按钮事件
  $('#confirm-import-btn')
    .off('click')
    .on('click', function () {
      // 导入确认逻辑
      const overwrite = $('#import-overwrite-check').is(':checked');
      // 实际导入操作
      $('#import-confirm-modal').modal('hide');
      cleanupModalBackdrops();
    });

  // 邮箱类型变化事件
  $('#email-type')
    .off('change')
    .on('change', function () {
      const type = $(this).val();
      if (type === 'tempemail') {
        $('#tempemail-fields').show();
        $('#zmail-fields').hide();
      } else {
        $('#tempemail-fields').hide();
        $('#zmail-fields').show();
      }
    });

  // 代理开关事件
  $('#use-proxy')
    .off('change')
    .on('change', function () {
      toggleProxySettings();
    });

  // 动态User-Agent开关事件
  $('#dynamic-useragent')
    .off('change')
    .on('change', function () {
      const useragentContainer = $('#useragent-input-container');
      if ($(this).is(':checked')) {
        useragentContainer.hide();
      } else {
        useragentContainer.show();
      }
    });

  // 邮箱代理开关事件
  $('#email-proxy-enabled')
    .off('change')
    .on('change', function () {
      const proxyAddressContainer = $('#email-proxy-address-container');
      if ($(this).is(':checked')) {
        proxyAddressContainer.show();
      } else {
        proxyAddressContainer.hide();
      }
    });
}

// 全局变量
let accounts = [];
let filteredAccounts = [];
let refreshTimer;

// 显示加载遮罩
function showLoading(message = '加载中，请稍候...') {
  // 如果遮罩已经显示，只更新消息
  const loadingOverlay = document.getElementById('loading-overlay');
  if (loadingOverlay.classList.contains('show')) {
    $('#loading-overlay p').text(message);
    return;
  }

  // 否则显示遮罩
  loadingOverlay.classList.add('show');
  $('#loading-overlay p').text(message);

  // 确保关闭按钮事件绑定 - 直接绑定不通过jQuery委托
  document.querySelector('.close-overlay').onclick = function () {
    hideLoading();
  };
}

// 隐藏加载遮罩
function hideLoading() {
  const loadingOverlay = document.getElementById('loading-overlay');
  loadingOverlay.classList.remove('show');
}

// 加载账号数据
function loadAccounts(
  page = 1,
  perPage = itemsPerPage,
  search = '',
  sortField = currentSortField,
  sortOrder = currentSortOrder,
  showLoadingOverlay = true
) {
  // 只在需要时显示加载遮罩
  if (showLoadingOverlay) {
    showLoading();
  }

  // 构建URL查询参数
  let params = new URLSearchParams({
    page: page,
    per_page: perPage,
    sort_by: sortField,
    order: sortOrder,
  });

  if (search) {
    params.append('search', search);
  }

  const url = `/accounts?${params.toString()}`;

  $.ajax({
    url: url,
    method: 'GET',
    success: function (response) {
      if (response.success) {
        accounts = response.data;

        // 更新分页和排序信息
        currentPage = response.pagination.page;
        totalPages = response.pagination.total_pages;
        itemsPerPage = response.pagination.per_page;
        currentSortField = response.sort.field;
        currentSortOrder = response.sort.order;

        // 新增：更新账号统计信息
        const totalAccounts = response.pagination.total_count || 0;
        const maxAccounts = parseInt($('#max-accounts').text()) || 10;
        const remainingSlots = Math.max(0, maxAccounts - totalAccounts);

        $('#current-count').text(totalAccounts);
        $('#remaining-slots').text(`剩余: ${remainingSlots}`);

        // 计算使用百分比
        const usagePercent =
          maxAccounts > 0 ? Math.round((totalAccounts / maxAccounts) * 100) : 0;

        // 更新进度条
        $('.battery-progress').attr('data-percent', usagePercent);
        $('.battery-percent').text(`${usagePercent}%`);

        // 更新排序控件
        $('#sort-field').val(currentSortField);
        $('#sort-order').val(currentSortOrder);

        // 添加淡入效果
        $('#accounts-table').css('opacity', 0);

        // 更新UI
        updateAccountsTable(accounts);
        updatePagination(currentPage, totalPages);
        $('#total-accounts').text(response.pagination.total_count);

        // 更新每页记录数下拉框
        $('#per-page').val(itemsPerPage);

        // 淡入表格
        $('#accounts-table').animate({ opacity: 1 }, 300);

        if (showLoadingOverlay) {
          hideLoading();
        }
      } else {
        if (showLoadingOverlay) {
          hideLoading();
        }
        showAlert('danger', '加载账号失败: ' + response.message);
      }
    },
    error: function (xhr) {
      if (showLoadingOverlay) {
        hideLoading();
      }
      showAlert(
        'danger',
        '加载账号失败: ' + (xhr.responseJSON?.detail || xhr.statusText)
      );
    },
  });
}

// 更新分页控件
function updatePagination(currentPage, totalPages) {
  // 清除现有页码
  $('.pagination .page-number').remove();

  // 决定显示哪些页码
  let pages = [];

  // 限制显示的页码数量，使UI更加紧凑
  if (totalPages <= 5) {
    // 总页数少于5，显示所有页码
    for (let i = 1; i <= totalPages; i++) {
      pages.push(i);
    }
  } else {
    // 总页数大于5，使用更紧凑的布局

    // 总是显示第一页
    pages.push(1);

    // 当前页在前3页
    if (currentPage <= 3) {
      pages.push(2, 3, 4, '...', totalPages);
    }
    // 当前页在后3页
    else if (currentPage >= totalPages - 2) {
      pages.push(
        '...',
        totalPages - 3,
        totalPages - 2,
        totalPages - 1,
        totalPages
      );
    }
    // 当前页在中间
    else {
      pages.push(
        '...',
        currentPage - 1,
        currentPage,
        currentPage + 1,
        '...',
        totalPages
      );
    }
  }

  // 创建页码元素 - 简化HTML生成
  let pageElements = '';

  pages.forEach((page) => {
    if (page === '...') {
      pageElements += `<li class="page-item disabled page-number"><a class="page-link" href="#">…</a></li>`;
    } else {
      const isActive = page === currentPage ? 'active' : '';
      pageElements += `<li class="page-item page-number ${isActive}"><a class="page-link" href="#" data-page="${page}">${page}</a></li>`;
    }
  });

  // 使用insertBefore而不是after，确保顺序正确
  $(pageElements).insertBefore('#next-page');

  // 更新上一页/下一页按钮状态
  $('#prev-page').toggleClass('disabled', currentPage === 1);
  $('#next-page').toggleClass('disabled', currentPage === totalPages);

  // 更新分页信息文本
  $('#current-page').text(currentPage);
  $('#total-pages').text(totalPages);
}

// 修复分页事件绑定 - 确保在DOM加载完成后绑定
function bindPaginationEvents() {
  // 上一页按钮 - 使用事件委托
  $(document).on('click', '#prev-page:not(.disabled) a', function (e) {
    e.preventDefault();
    if (currentPage > 1) {
      loadAccounts(currentPage - 1, itemsPerPage, $('#search-input').val());
    }
  });

  // 下一页按钮 - 使用事件委托
  $(document).on('click', '#next-page:not(.disabled) a', function (e) {
    e.preventDefault();
    if (currentPage < totalPages) {
      loadAccounts(currentPage + 1, itemsPerPage, $('#search-input').val());
    }
  });

  // 页码点击 - 使用事件委托确保动态生成的元素也能响应
  $(document).on(
    'click',
    '.page-number:not(.disabled) .page-link',
    function (e) {
      e.preventDefault();
      const page = parseInt($(this).attr('data-page'));
      if (!isNaN(page)) {
        loadAccounts(page, itemsPerPage, $('#search-input').val());
      }
    }
  );

  // 每页显示记录数变更
  $(document).on('change', '#per-page', function () {
    itemsPerPage = parseInt($(this).val());
    loadAccounts(1, itemsPerPage, $('#search-input').val());
  });
}

// 修改搜索函数
function filterAccounts() {
  const searchTerm = $('#search-input').val().trim();
  loadAccounts(1, itemsPerPage, searchTerm);
}

// 更新账号表格
function updateAccountsTable(accounts) {
  const accountsBody = $('#accounts-tbody');
  accountsBody.empty();

  // 计算当前页的起始索引
  const startIndex = (currentPage - 1) * itemsPerPage;

  // 确保每个账号都有ID并且所有字段都有值
  accounts.forEach((account, index) => {
    if (!account.id) account.id = Date.now() + index;

    // 确保所有字段都不为undefined，防止jQuery错误
    account.email = account.email || '';
    account.token = account.token || '';
    account.password = account.password || '';
    account.status = account.status || 'active';
    account.usage_limit = account.usage_limit || '';
    account.created_at = account.created_at || '';
    account.user = account.user || '';
  });

  // 如果没有数据，显示空状态
  if (accounts.length === 0) {
    accountsBody.html(`
      <tr>
        <td colspan="7" class="text-center py-4">
          <div class="py-5">
            <i class="fas fa-inbox fa-3x text-muted mb-3"></i>
            <p class="text-muted">暂无账号数据</p>
          </div>
        </td>
      </tr>
    `);
    return;
  }

  // 渲染每行数据
  accounts.forEach((account, index) => {
    // 完整的行模板，包含所有单元格内容
    const row = `
            <tr id="account-row-${account.id}" data-account-id="${
      account.id
    }" data-status="${account.status}" 
                class="${
                  account.status === 'deleted'
                    ? 'table-danger'
                    : account.status === 'disabled'
                    ? 'table-warning'
                    : ''
                }">
                <td class="d-none d-md-table-cell">${
                  startIndex + index + 1
                }</td>
                <td class="email-column">
                    ${account.email}
                    <span class="badge ${
                      account.status === 'active'
                        ? 'bg-success'
                        : account.status === 'disabled'
                        ? 'bg-warning'
                        : 'bg-danger'
                    } ms-2">
                        ${
                          account.status === 'active'
                            ? '正常'
                            : account.status === 'disabled'
                            ? '停用'
                            : '删除'
                        }
                    </span>
                </td>
                <td class="d-none d-lg-table-cell password-cell">
                    <span class="password-text">${maskPassword(
                      account.password
                    )}</span>
                    <i class="fas fa-eye toggle-password" data-password="${
                      account.password
                    }" title="显示/隐藏密码"></i>
                    <i class="fas fa-copy copy-btn ms-1" data-copy="${
                      account.password
                    }" title="复制密码"></i>
                </td>
                ${renderTokenColumn(account.token, account.id, account.email)}
                ${renderUsageProgress(account.usage_limit)}
                <td class="d-none d-lg-table-cell">
                    ${account.created_at || '未知'}
                </td>
                <td>
                    <div class="btn-group">
                        <button class="btn btn-sm btn-outline-primary get-usage-btn" data-email="${
                          account.email
                        }" title="查询使用量">
                            <i class="fas fa-chart-pie"></i>
                        </button>
                    </div>
                </td>
                <td class="operation-column">
                    <div class="d-flex flex-wrap gap-1">
                        ${
                          account.status !== 'active'
                            ? `<button class="btn btn-sm btn-outline-success status-action" data-email="${account.email}" data-id="${account.id}" data-status="active" title="设为正常">
                                <i class="fas fa-check-circle"></i>
                            </button>`
                            : ''
                        }
                            
                        ${
                          account.status !== 'disabled'
                            ? `<button class="btn btn-sm btn-outline-warning status-action" data-email="${account.email}" data-id="${account.id}" data-status="disabled" title="停用账号">
                                <i class="fas fa-pause-circle"></i>
                            </button>`
                            : ''
                        }
                            
                        ${
                          account.status !== 'deleted'
                            ? `<button class="btn btn-sm btn-outline-danger status-action" data-email="${account.email}" data-id="${account.id}" data-status="deleted" title="标记删除">
                                <i class="fas fa-times-circle"></i>
                            </button>`
                            : ''
                        }
                            
                        <button class="btn btn-sm btn-danger delete-account-btn" data-email="${
                          account.email
                        }" data-id="${account.id}" title="永久删除">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    accountsBody.append(row);
  });

  // 绑定事件
  bindTableEvents();

  // 更新表头排序指示
  $('.sortable').removeClass('asc desc');
  $(`.sortable[data-field="${currentSortField}"]`).addClass(currentSortOrder);
}

// 渲染账号表格
function renderAccountsTable() {
  const accountsBody = $('#accounts-tbody');
  accountsBody.empty();

  if (filteredAccounts.length === 0) {
    // 添加空状态提示
    accountsBody.html(`
            <tr>
                <td colspan="7" class="text-center py-4">
                    <div class="py-5">
                        <i class="fas fa-inbox fa-3x text-muted mb-3"></i>
                        <p class="text-muted">暂无账号数据</p>
                    </div>
                </td>
            </tr>
        `);
    return;
  }

  // 计算当前页的数据
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = Math.min(startIndex + itemsPerPage, filteredAccounts.length);
  const currentPageData = filteredAccounts.slice(startIndex, endIndex);

  // 确保每个账号对象的字段都有值
  currentPageData.forEach((account, index) => {
    if (!account.id) account.id = Date.now() + index;
    account.email = account.email || '';
    account.token = account.token || '';
    account.password = account.password || '';
    account.status = account.status || 'active';
    account.usage_limit = account.usage_limit || '';
    account.created_at = account.created_at || '';
  });

  // 渲染每行数据
  currentPageData.forEach((account, index) => {
    // 完整的行模板，包含所有单元格内容
    const row = `
            <tr id="account-row-${account.id}" data-status="${account.status}" 
                class="${
                  account.status === 'deleted'
                    ? 'table-danger'
                    : account.status === 'disabled'
                    ? 'table-warning'
                    : ''
                }">
                <td class="d-none d-md-table-cell">${
                  startIndex + index + 1
                }</td>
                <td class="email-column">
                    ${account.email}
                    <span class="badge ${
                      account.status === 'active'
                        ? 'bg-success'
                        : account.status === 'disabled'
                        ? 'bg-warning'
                        : 'bg-danger'
                    } ms-2">
                        ${
                          account.status === 'active'
                            ? '正常'
                            : account.status === 'disabled'
                            ? '停用'
                            : '删除'
                        }
                    </span>
                </td>
                <td class="d-none d-lg-table-cell password-cell">
                    <span class="password-text">${maskPassword(
                      account.password
                    )}</span>
                    <i class="fas fa-eye toggle-password" data-password="${
                      account.password
                    }" title="显示/隐藏密码"></i>
                    <i class="fas fa-copy copy-btn ms-1" data-copy="${
                      account.password
                    }" title="复制密码"></i>
                </td>
                ${renderTokenColumn(account.token, account.id, account.email)}
                ${renderUsageProgress(account.usage_limit)}
                <td class="d-none d-lg-table-cell">
                    ${account.created_at || '未知'}
                </td>
                <td>
                    <div class="btn-group">
                        <button class="btn btn-sm btn-outline-primary get-usage-btn" data-email="${
                          account.email
                        }" title="查询使用量">
                            <i class="fas fa-chart-pie"></i>
                        </button>
                    </div>
                </td>
                <td class="operation-column">
                    <div class="d-flex flex-wrap gap-1">
                        ${
                          account.status !== 'active'
                            ? `<button class="btn btn-sm btn-outline-success status-action" data-email="${account.email}" data-id="${account.id}" data-status="active" title="设为正常">
                                <i class="fas fa-check-circle"></i>
                            </button>`
                            : ''
                        }
                            
                        ${
                          account.status !== 'disabled'
                            ? `<button class="btn btn-sm btn-outline-warning status-action" data-email="${account.email}" data-id="${account.id}" data-status="disabled" title="停用账号">
                                <i class="fas fa-pause-circle"></i>
                            </button>`
                            : ''
                        }
                            
                        ${
                          account.status !== 'deleted'
                            ? `<button class="btn btn-sm btn-outline-danger status-action" data-email="${account.email}" data-id="${account.id}" data-status="deleted" title="标记删除">
                                <i class="fas fa-times-circle"></i>
                            </button>`
                            : ''
                        }
                            
                        <button class="btn btn-sm btn-danger delete-account-btn" data-email="${
                          account.email
                        }" data-id="${account.id}" title="永久删除">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    accountsBody.append(row);
  });

  // 绑定事件
  bindTableEvents();
  renderPagination();
}

// 渲染分页
function renderPagination() {
  const totalPages = Math.ceil(filteredAccounts.length / itemsPerPage);
  const pagination = $('#pagination');
  pagination.empty();

  if (totalPages <= 1) {
    return;
  }

  const paginationNav = $('<nav aria-label="Page navigation"></nav>');
  const paginationUl = $('<ul class="pagination"></ul>');

  // 上一页按钮
  paginationUl.append(`
        <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
            <a class="page-link" href="#" aria-label="Previous" ${
              currentPage !== 1
                ? 'onclick="changePage(' +
                  (currentPage - 1) +
                  '); return false;"'
                : ''
            }>
                <span aria-hidden="true">&laquo;</span>
            </a>
        </li>
    `);

  // 页码按钮
  for (let i = 1; i <= totalPages; i++) {
    paginationUl.append(`
            <li class="page-item ${currentPage === i ? 'active' : ''}">
                <a class="page-link" href="#" onclick="changePage(${i}); return false;">${i}</a>
            </li>·
        `);
  }

  // 下一页按钮
  paginationUl.append(`
        <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
            <a class="page-link" href="#" aria-label="Next" ${
              currentPage !== totalPages
                ? 'onclick="changePage(' +
                  (currentPage + 1) +
                  '); return false;"'
                : ''
            }>
                <span aria-hidden="true">&raquo;</span>
            </a>
        </li>
    `);

  paginationNav.append(paginationUl);
  pagination.append(paginationNav);
}

// 更改页码
function changePage(page) {
  currentPage = page;
  renderAccountsTable();
}

// 获取账号用量详情并更新数据库
function getAccountUsage(email) {
  showLoading();
  fetch(`/account/${encodeURIComponent(email)}/usage`)
    .then((res) => res.json())
    .then((data) => {
      hideLoading();
      if (data.success) {
        // 创建并显示用量信息模态框
        const modal = $(`
                    <div class="modal fade usage-modal" tabindex="-1">
                        <div class="modal-dialog">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h5 class="modal-title">账号用量信息</h5>
                                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                                </div>
                                <div class="modal-body">
                                    <div class="mb-3">
                                        <strong>邮箱:</strong> ${data.email}
                                    </div>
                                    <div class="mb-3">
                                        <strong>剩余额度:</strong> ${
                                          data.usage.remaining_balance !== null
                                            ? data.usage.remaining_balance
                                            : '未知'
                                        }
                                    </div>
                                    <div class="mb-3">
                                        <strong>剩余天数:</strong> ${
                                          data.usage.remaining_days !== null
                                            ? data.usage.remaining_days
                                            : '未知'
                                        }
                                    </div>
                                    <div class="mb-3">
                                        <strong>状态:</strong> 
                                        <span class="badge ${
                                          data.usage.status === 'active'
                                            ? 'bg-success'
                                            : 'bg-danger'
                                        }">
                                            ${
                                              data.usage.status === 'active'
                                                ? '活跃'
                                                : '不活跃'
                                            }
                                        </span>
                                    </div>
                                    <div class="mt-3 text-muted small">
                                        <strong>更新时间:</strong> ${formatDateTime(
                                          data.timestamp
                                        )}
                                    </div>
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                                </div>
                            </div>
                        </div>
                    </div>
                `);

        $('body').append(modal);
        const modalInstance = new bootstrap.Modal(modal[0]);
        modalInstance.show();

        // 模态框关闭时移除DOM并清理背景
        modal[0].addEventListener('hidden.bs.modal', function () {
          modal.remove();
          cleanupModalBackdrops();
        });
      }
    })
    .catch((error) => {
      console.error('获取账号用量失败:', error);
      showAlert('获取账号用量失败', 'danger');
      hideLoading();
    });
}

// 更新账号用量到数据库
function updateAccountUsageLimit(email, usageLimit) {
  fetch(`/account/${encodeURIComponent(email)}/update-usage`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ usage_limit: usageLimit }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.success) {
        console.log(`账号 ${email} 用量数据已更新到数据库`);
      } else {
        console.error(`更新账号 ${email} 用量数据失败:`, data.message);
      }
    })
    .catch((error) => {
      console.error(`更新账号 ${email} 用量数据时发生错误:`, error);
    });
}

// 修复任务状态更新问题
function startTaskManually() {
  showLoading();

  // 清除自定义邮箱注册标记
  window.customEmailRegistration = false;

  fetch('/registration/start', {
    method: 'GET',
  })
    .then((res) => res.json())
    .then((data) => {
      hideLoading();
      if (data.success) {
        showAlert('定时任务已成功启动', 'success');
        checkTaskStatus();

        // 清除可能存在的验证码提示
        $('#verification-tip-alert').hide();

        // 短暂延迟后再启动验证码检查，确保UI已更新
        setTimeout(() => {
          // 启动验证码检查
          startVerificationCodeCheck();
          showAlert(
            '任务注册已启动，系统将自动处理验证码，如需手动输入将会提示',
            'info'
          );
        }, 500);
      } else {
        showAlert(`启动任务失败: ${data.message || '未知错误'}`, 'danger');
      }
    })
    .catch((error) => {
      console.error('启动任务时发生错误:', error);
      hideLoading();
      showAlert('启动任务失败，请稍后重试', 'danger');
    });
}

// 同样添加到停止任务函数
function stopTaskManually() {
  showLoading();
  fetch('/registration/stop', {
    method: 'GET',
  })
    .then((res) => res.json())
    .then((data) => {
      hideLoading();
      if (data.success) {
        showAlert('定时任务已成功停止', 'success');

        // 隐藏验证码提示框
        $('#verification-tip-alert').hide();

        // 立即更新任务状态 - 添加这段代码
        fetch('/registration/status')
          .then((res) => res.json())
          .then((statusData) => {
            updateTaskStatusUI(statusData);
          });

        // 停止验证码检查
        stopVerificationCodeCheck();
      } else {
        showAlert(`停止任务失败: ${data.message || '未知错误'}`, 'danger');
      }
    })
    .catch((error) => {
      console.error('停止任务时发生错误:', error);
      hideLoading();
      showAlert('停止任务失败，请稍后重试', 'danger');
    });
}

// 复制到剪贴板
function copyToClipboard(text) {
  navigator.clipboard
    .writeText(text)
    .then(() => {
      showAlert('复制成功，Token已复制到剪贴板', 'success');
    })
    .catch((err) => {
      console.error('复制失败:', err);
      showAlert('复制失败', 'danger');
    });
}

// 显示通知
function showAlert(message, type, isSpecial = false) {
  const alertId = 'alert-' + Date.now();
  const alertClass = isSpecial
    ? `alert-${type} special-alert animate__animated animate__bounceIn`
    : `alert-${type} animate__animated animate__fadeInRight`;

  const alert = $(`
        <div id="${alertId}" class="alert ${alertClass} alert-dismissible fade show" role="alert">
            ${isSpecial ? '<i class="fas fa-star me-2"></i>' : ''}${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `);

  $('#alert-container').append(alert);

  // 5秒后自动消失
  setTimeout(() => {
    $(`#${alertId}`).alert('close');
  }, 5000);
}

// 日期时间格式化
function formatDateTime(dateTimeString) {
  if (!dateTimeString) return '-';

  try {
    const date = new Date(dateTimeString);
    if (isNaN(date.getTime())) return dateTimeString;

    const year = date.getFullYear();
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const seconds = date.getSeconds().toString().padStart(2, '0');

    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
  } catch (error) {
    return dateTimeString;
  }
}

// 修改掩码函数，增加对用户名的特殊处理
function maskText(text, showChars = 6, isUsername = false) {
  if (!text) return '';

  // 用户名特殊处理 - 只显示前1/3
  if (isUsername) {
    const showLength = Math.ceil(text.length / 3);
    if (text.length <= showLength) return text;
    return `${text.substring(0, showLength)}...`;
  }

  // 其他文本使用标准处理
  if (text.length <= showChars) return text;
  return `${text.substring(0, showChars)}...`;
}

// 隐藏密码
function maskPassword(password) {
  if (!password) return '';
  return '•'.repeat(password.length);
}

// 页面加载动画
document.addEventListener('DOMContentLoaded', function () {
  // 默认隐藏验证码提示框
  $('#verification-tip-alert').hide();

  // 修改动画类添加代码，删除对已删除元素的引用
  const elements = [
    { selector: '.card', animation: 'animate__fadeIn', delay: 0.2 },
  ];

  elements.forEach((item) => {
    const elems = document.querySelectorAll(item.selector);
    elems.forEach((el, index) => {
      el.classList.add('animate__animated', item.animation);

      if (item.delay) {
        const delay = item.stagger ? item.delay * (index + 1) : item.delay;
        el.style.animationDelay = `${delay}s`;
      }
    });
  });
});

// 烟花动画实现
const Fireworks = {
  canvas: null,
  ctx: null,
  particles: [],

  init: function () {
    this.canvas = document.getElementById('fireworks-canvas');
    this.ctx = this.canvas.getContext('2d');
    this.resizeCanvas();
    window.addEventListener('resize', () => this.resizeCanvas());
  },

  resizeCanvas: function () {
    this.canvas.width = window.innerWidth;
    this.canvas.height = window.innerHeight;
  },

  start: function () {
    this.canvas.style.display = 'block';
    this.particles = [];

    // 创建5次烟花，间隔300ms
    for (let i = 0; i < 5; i++) {
      setTimeout(() => {
        const x = Math.random() * this.canvas.width;
        const y = Math.random() * this.canvas.height * 0.6;
        this.createParticles(x, y);
      }, i * 300);
    }

    this.animate();

    // 5秒后停止动画
    setTimeout(() => {
      this.canvas.style.display = 'none';
    }, 5000);
  },

  createParticles: function (x, y) {
    const colors = ['#ff595e', '#ffca3a', '#8ac926', '#1982c4', '#6a4c93'];

    for (let i = 0; i < 80; i++) {
      const particle = {
        x: x,
        y: y,
        size: Math.random() * 4 + 1,
        color: colors[Math.floor(Math.random() * colors.length)],
        velocity: {
          x: (Math.random() - 0.5) * 8,
          y: (Math.random() - 0.5) * 8,
        },
        alpha: 1,
        decay: Math.random() * 0.02 + 0.01,
      };

      this.particles.push(particle);
    }
  },

  animate: function () {
    if (this.particles.length === 0) return;

    requestAnimationFrame(() => this.animate());

    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    for (let i = 0; i < this.particles.length; i++) {
      const p = this.particles[i];

      // 添加重力
      p.velocity.y += 0.05;

      // 更新位置
      p.x += p.velocity.x;
      p.y += p.velocity.y;

      // 减少透明度
      p.alpha -= p.decay;

      // 绘制粒子
      this.ctx.save();
      this.ctx.globalAlpha = p.alpha;
      this.ctx.fillStyle = p.color;
      this.ctx.beginPath();
      this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      this.ctx.fill();
      this.ctx.restore();

      // 移除消失的粒子
      if (p.alpha <= 0) {
        this.particles.splice(i, 1);
        i--;
      }
    }
  },
};

// 初始化烟花
Fireworks.init();

// 绑定表格交互事件
function bindTableEvents() {
  // 显示/隐藏用户名
  $('.toggle-username')
    .off('click')
    .on('click', function () {
      const username = $(this).data('username');
      const usernameText = $(this).prev('.username-text');

      if (usernameText.text() === username) {
        usernameText.text(maskText(username, 6, true));
      } else {
        usernameText.text(username);
      }
    });

  // 显示/隐藏密码
  $('.toggle-password')
    .off('click')
    .on('click', function () {
      const password = $(this).data('password');
      const passwordText = $(this).prev('.password-text');

      if (passwordText.text() === password) {
        passwordText.text(maskPassword(password));
      } else {
        passwordText.text(password);
      }
    });

  // 显示/隐藏Token
  $('.toggle-token')
    .off('click')
    .on('click', function () {
      const token = $(this).data('token');
      const tokenText = $(this).prev('.token-text');

      if (tokenText.text() === token) {
        tokenText.text(maskText(token));
      } else {
        tokenText.text(token);
      }
    });

  // 查看Token按钮
  $('.view-token-btn')
    .off('click')
    .on('click', function () {
      const token = $(this).data('token') || '';
      const accountId =
        $(this).attr('data-account-id') ||
        $(this).closest('tr').data('account-id') ||
        Date.now();

      // 确保token不为空
      if (!token) {
        showAlert('Token数据为空或无效', 'danger');
        return;
      }

      // 设置模态框内容
      $('#tokenFullText').val(token);

      // 确保使用DOM原生方法设置属性，避免jQuery缓存问题
      document
        .getElementById('useTokenBtn')
        .setAttribute('data-account-id', String(accountId));

      // 确保每次打开模态框时都重新绑定复制按钮事件
      $('#copyTokenBtn')
        .off('click')
        .on('click', function () {
          const textToCopy = $('#tokenFullText').val();
          copyToClipboard(textToCopy);
        });

      new bootstrap.Modal(document.getElementById('tokenViewModal')).show();
    });

  // 复制按钮
  $('.copy-btn')
    .off('click')
    .on('click', function () {
      const textToCopy = $(this).data('copy');
      copyToClipboard(textToCopy);
    });

  // 获取用量按钮
  $('.get-usage-btn')
    .off('click')
    .on('click', function () {
      const email = $(this).data('email');
      getAccountUsage(email);
    });

  // 查看使用记录按钮
  $('.view-records-btn')
    .off('click')
    .on('click', function () {
      const email = $(this).data('email');
      const id = $(this).data('id');
      getAccountUsageRecords(email, id);
    });

  // 删除按钮
  $('.delete-account-btn')
    .off('click')
    .on('click', function () {
      const email = $(this).data('email');
      const id = $(this).data('id');

      // 检查ID是否有效
      if (!id) {
        showAlert('无法删除：账号ID无效', 'danger');
        return;
      }

      // 设置确认对话框的值
      $('#deleteEmailConfirm').text(email);
      $('#deleteIdConfirm').text(id);
      $('#deleteAccountId').val(id);

      // 显示删除确认对话框
      const deleteModal = new bootstrap.Modal(
        document.getElementById('deleteConfirmModal')
      );
      deleteModal.show();
    });

  // 状态操作按钮
  $('.status-action')
    .off('click')
    .on('click', function (e) {
      e.preventDefault();
      const email = $(this).data('email');
      const id = $(this).data('id');
      const status = $(this).data('status');
      updateAccountStatus(email, id, status);
    });
}

// 更新删除确认按钮事件处理
function deleteAccount() {
  const accountId = $('#deleteAccountId').val();
  const email = $('#deleteEmailConfirm').text();

  if (!accountId || accountId === '无') {
    showAlert('账号ID无效，无法执行删除操作', 'danger');
    return;
  }

  showLoading('账号删除中...');

  // 构建API URL
  const apiUrl = `/account/id/${accountId}?hard_delete=true`;

  fetch(apiUrl, {
    method: 'DELETE',
  })
    .then((res) => res.json())
    .then((data) => {
      $('#deleteConfirmModal').modal('hide');
      cleanupModalBackdrops(); // 添加清理
      hideLoading();

      if (data.success) {
        showAlert(`账号 ${email} 已成功删除`, 'success');
        // 重新加载账号列表
        loadAccounts(currentPage, itemsPerPage);
      } else {
        showAlert(`删除失败: ${data.message || '未知错误'}`, 'danger');
      }
    })
    .catch((error) => {
      console.error('删除账号时发生错误:', error);
      $('#deleteConfirmModal').modal('hide');
      cleanupModalBackdrops(); // 添加清理
      hideLoading();
      showAlert('删除账号失败，请稍后重试', 'danger');
    });
}

// 修改updateAccountStatus函数，确保正确发送请求体
function updateAccountStatus(email, id, status) {
  showLoading();
  // 优先使用ID API，如果ID存在的话
  const apiUrl = id
    ? `/account/id/${id}/status`
    : `/account/${encodeURIComponent(email)}/status`;

  fetch(apiUrl, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ status: status }), // 确保这里的字段名是status
  })
    .then((res) => res.json())
    .then((data) => {
      hideLoading();
      if (data.success) {
        let statusText = '';
        if (status === 'active') statusText = '正常';
        else if (status === 'disabled') statusText = '停用';
        else if (status === 'deleted') statusText = '删除';

        showAlert(
          `账号${
            id ? '(ID:' + id + ')' : ''
          } ${email} 已成功设置为${statusText}状态`,
          'success'
        );
        loadAccounts(1, itemsPerPage);
      } else {
        showAlert(`更新账号状态失败: ${data.message || '未知错误'}`, 'danger');
      }
    })
    .catch((error) => {
      console.error('更新账号状态时发生错误:', error);
      hideLoading();
      showAlert('更新账号状态失败，请稍后重试', 'danger');
    });
}

// 完全重构额度显示函数，精确匹配参考代码
function renderUsageProgress(usageLimit) {
  // 计算使用进度
  const premiumUsed = 150 - usageLimit;
  const premiumTotal = 150;
  const premiumRemaining = premiumTotal - premiumUsed;
  const premiumPercent = Math.round((premiumUsed / premiumTotal) * 100);

  return `
        <td class="usage-info">
            <div class="usage-numbers">
                <span class="used-count">${premiumUsed}</span>
                <span class="separator">/</span>
                <span class="total-count">${premiumTotal}</span>
                <span class="remaining-count">(剩余: ${premiumRemaining})</span>
            </div>
            <div class="battery-progress" data-percent="${
              Math.round(premiumPercent / 10) * 10
            }">
                <div class="battery-bars">
                    <span class="battery-bar"></span>
                    <span class="battery-bar"></span>
                    <span class="battery-bar"></span>
                    <span class="battery-bar"></span>
                    <span class="battery-bar"></span>
                    <span class="battery-bar"></span>
                    <span class="battery-bar"></span>
                    <span class="battery-bar"></span>
                    <span class="battery-bar"></span>
                    <span class="battery-bar"></span>
                </div>
                <span class="battery-percent">${premiumPercent}%</span>
            </div>
        </td>
    `;
}

// 修改Token列的渲染方式
function renderTokenColumn(token, accountId, email) {
  // 确保所有参数都有默认值，防止undefined
  const safeToken = token || '';
  const safeAccountId = accountId || Date.now();
  const safeEmail = email || '';

  return `
        <td class="token-column">
            <button class="btn btn-sm btn-outline-info view-token-btn" data-token="${safeToken}" data-account-id="${safeAccountId}">
                <i class="fas fa-eye"></i> 查看Token
            </button>
            <button class="btn btn-sm btn-outline-info view-records-btn" data-email="${email}" data-id="${safeAccountId}" title="查看使用记录">
                <i class="fas fa-history"></i>
            </button>
        </td>
    `;
}

// 加载配置函数
function loadConfig() {
  showLoading();
  $.ajax({
    url: '/config',
    method: 'GET',
    success: function (response) {
      if (response.success) {
        const config = response.data;

        // 现有字段设置...

        // 设置代理配置
        $('#use-proxy').prop('checked', config.USE_PROXY === 'True');
        $('#proxy-type').val(config.PROXY_TYPE || 'http');
        $('#proxy-host').val(config.PROXY_HOST || '');
        $('#proxy-port').val(config.PROXY_PORT || '');
        $('#proxy-timeout').val(config.PROXY_TIMEOUT || '10');
        $('#proxy-username').val(config.PROXY_USERNAME || '');
        $('#proxy-password').val(config.PROXY_PASSWORD || '');

        // 触发动态UA的change事件
        $('#dynamic-useragent').trigger('change');
        // 根据是否启用代理来显示/隐藏代理设置
        toggleProxySettings();

        $('#browser-useragent').val(config.BROWSER_USER_AGENT);
        $('#accounts-limit').val(config.MAX_ACCOUNTS);
        $('#captcha-method').val(config.EMAIL_CODE_TYPE || 'API');
        $('#email-domains').val(config.EMAIL_DOMAINS);
        $('#email-username').val(config.EMAIL_USERNAME);
        $('#email-pin').val(config.EMAIL_PIN);
        $('#browser-path').val(config.BROWSER_PATH || '');
        $('#cursor-path').val(config.CURSOR_PATH || '');

        if (config.EMAIL_DOMAIN) {
          // 获取第一个域名作为示例
          const firstDomain = config.EMAIL_DOMAIN;
          // 更新输入框提示
          $('#email-username').attr(
            'placeholder',
            `仅输入用户名部分，例如：ddcat28（完整地址将是 ddcat28@${firstDomain}）`
          );
          // 添加域名显示标签
          if (!$('#email-domain-suffix').length) {
            $('#email-username').after(
              `<span id="email-domain-suffix" class="input-group-text bg-light">@${firstDomain}</span>`
            );
            // 将输入框和域名标签包装在input-group中
            $('#email-username, #email-domain-suffix').wrapAll(
              '<div class="input-group"></div>'
            );
          } else {
            $('#email-domain-suffix').text(`@${firstDomain}`);
          }
        }

        $('#email-type').val(config.EMAIL_TYPE);
        $('#email-proxy-enabled').prop(
          'checked',
          config.EMAIL_PROXY_ENABLED || false
        );
        if (config.EMAIL_PROXY_ENABLED) {
          $('#email-proxy-address').val(config.EMAIL_PROXY_ADDRESS);
          $('#email-api').val(config.EMAIL_API);
        }
        if (config.EMAIL_TYPE == 'tempemail') {
          $('#tempemail-fields').show();
          $('#zmail-fields').hide();
        } else if (config.EMAIL_TYPE == 'zmail') {
          $('#tempemail-fields').hide();
          $('#zmail-fields').show();
        }

        // 配置加载完毕后，立即更新任务状态显示
        checkTaskStatus();

        hideLoading();
      } else {
        showAlert('danger', '加载配置失败: ' + response.message);
        hideLoading();
      }
    },
    error: function (xhr) {
      hideLoading();
      showAlert('danger', '加载配置失败: ' + xhr.statusText);
    },
  });
}

// 添加代理设置的显示/隐藏控制
function toggleProxySettings() {
  if ($('#use-proxy').is(':checked')) {
    $('#proxy-settings').show();
  } else {
    $('#proxy-settings').hide();
  }
}

// 添加配置保存回调，支持重启
function saveConfig() {
  showLoading();
  // 修复：不依赖this上下文，直接获取动态UA的状态
  const isDynamicUA = $('#dynamic-useragent').is(':checked');
  const configData = {
    BROWSER_HEADLESS: $('#browser-headless').val() === 'true',
    DYNAMIC_USERAGENT: isDynamicUA,
    BROWSER_USER_AGENT: isDynamicUA ? '' : $('#browser-useragent').val(),
    MAX_ACCOUNTS: parseInt($('#accounts-limit').val()),
    EMAIL_CODE_TYPE: $('#captcha-method').val(),
    EMAIL_DOMAINS: $('#email-domains').val(),
    EMAIL_USERNAME: $('#email-username').val(),
    EMAIL_PIN: $('#email-pin').val(),
    BROWSER_PATH: $('#browser-path').val(),
    CURSOR_PATH: $('#cursor-path').val(),
    // 代理设置（确保这些字段存在）
    USE_PROXY: $('#use-proxy').is(':checked'),
    PROXY_TYPE: $('#proxy-type').val(),
    PROXY_HOST: $('#proxy-host').val(),
    PROXY_PORT: $('#proxy-port').val(),
    PROXY_TIMEOUT: parseInt($('#proxy-timeout').val()) || 10,
    PROXY_USERNAME: $('#proxy-username').val(),
    PROXY_PASSWORD: $('#proxy-password').val(),
  };

  $.ajax({
    url: '/config',
    method: 'POST',
    contentType: 'application/json',
    data: JSON.stringify(configData),
    success: function (response) {
      hideLoading();
      if (response.success) {
        // 保存成功后立即更新任务状态显示
        checkTaskStatus();

        // 添加重启询问提示
        showConfirmDialog(
          '配置已成功保存',
          '需要重启服务才能使更改生效。是否立即重启服务？',
          function () {
            // 确认重启
            restartService();
          }
        );
        enableConfigForm(false);
      } else {
        showAlert('danger', '保存配置失败: ' + response.message);
      }
    },
    error: function (xhr) {
      hideLoading();
      showAlert('danger', '保存配置失败: ' + xhr.statusText);
    },
  });
}

// 添加确认对话框函数
function showConfirmDialog(title, message, confirmCallback) {
  // 如果已存在对话框，先移除
  if ($('#confirm-dialog').length) {
    $('#confirm-dialog').remove();
  }

  const dialogHTML = `
        <div class="modal fade" id="confirm-dialog" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">${title}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">${message}</div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                        <button type="button" class="btn btn-primary" id="confirm-yes">确认</button>
                    </div>
                </div>
            </div>
        </div>
    `;

  $('body').append(dialogHTML);

  const modal = new bootstrap.Modal(document.getElementById('confirm-dialog'));
  modal.show();

  $('#confirm-yes').click(function () {
    modal.hide();
    if (typeof confirmCallback === 'function') {
      confirmCallback();
    }
  });
}

// 更新重启服务函数
function restartService() {
  showLoading('服务正在重新配置，请稍候...');

  $.ajax({
    url: '/restart',
    method: 'POST',
    success: function (response) {
      if (response.success) {
        // 显示成功消息
        hideLoading();
        showAlert(
          'success',
          response.message || '服务配置已更新，正在刷新页面...'
        );

        // 延迟3秒后刷新页面
        setTimeout(function () {
          window.location.reload();
        }, 3000);
      } else {
        hideLoading();
        showAlert(
          'danger',
          '重启服务失败: ' + (response.message || '未知错误')
        );
      }
    },
    error: function (xhr) {
      hideLoading();
      showAlert('danger', '重启服务请求失败，请手动刷新页面');

      // 延迟5秒后尝试刷新页面
      setTimeout(function () {
        window.location.reload();
      }, 5000);
    },
  });
}

// 启用/禁用配置表单
function enableConfigForm(enable) {
  const inputs = $('#config-form select, #config-form input');
  if (enable) {
    inputs.prop('disabled', false);
    // 如果动态UA已启用，保持UA输入框禁用
    if ($('#dynamic-useragent').prop('checked')) {
      $('#browser-useragent').prop('disabled', true);
    }
    // 显示按钮容器而不是单个按钮
    $('#config-actions').show();
    $('#edit-config-btn').hide();
  } else {
    inputs.prop('disabled', true);
    // 隐藏按钮容器
    $('#config-actions').hide();
    $('#edit-config-btn').show();
  }
}

// 动态User-Agent切换逻辑
$('#dynamic-useragent').change(function () {
  const isDynamicUA = $(this).prop('checked');
  if (isDynamicUA) {
    $('#browser-useragent').prop('disabled', true);
    $('#useragent-input-container').addClass('text-muted');
  } else {
    // 只有在编辑模式下才启用输入框
    const isEditMode = !$('#edit-config-btn').is(':visible');
    $('#browser-useragent').prop('disabled', !isEditMode);
    $('#useragent-input-container').removeClass('text-muted');
  }
});

// 修改任务状态显示函数，保留状态处理逻辑
function updateTaskStatusDisplay(statusData) {
  // 获取UI元素引用
  const statusBadge = $('#registration-status');
  const taskStatusText = $('#task-status-text');
  const taskIcon = $('#task-status i');

  // 直接使用服务器返回的统计数据
  const stats = statusData;

  // 计算实际使用的账号数量
  const usedCount = stats.active_count || 0;
  const maxAccounts = stats.max_accounts || 10;
  const remainingSlots = Math.max(0, maxAccounts - usedCount);
  // 更新显示
  $('#current-count').text(usedCount);
  $('#max-accounts').text(maxAccounts);
  $('#remaining-slots').text(`剩余: ${remainingSlots}`);
  // 计算使用百分比
  const usagePercent =
    maxAccounts > 0 ? Math.round((usedCount / maxAccounts) * 100) : 0;

  // 更新进度条
  $('.battery-progress').attr('data-percent', usagePercent);
  $('.battery-percent').text(`${usagePercent}%`);

  // 更新任务详情
  if (statusData.registration_details) {
    const details = statusData.registration_details;
    // 更新统计信息
    if (details.statistics) {
      $('#total-runs').text(details.statistics.total_runs);
      $('#successful-runs').text(details.statistics.successful_runs);
      $('#failed-runs').text(details.statistics.failed_runs);
      $('#success-rate').text(details.statistics.success_rate);
    }
  }

  // 根据任务状态更新UI
  switch (statusData.task_status) {
    case 'running':
      statusBadge
        .removeClass('bg-success bg-warning bg-danger')
        .addClass('bg-primary');
      statusBadge.text('运行中');
      taskStatusText.text(statusData.status_message || '任务正在运行中');
      taskIcon
        .removeClass('fa-check-circle fa-pause-circle fa-times-circle')
        .addClass('fa-spinner fa-spin');
      taskIcon
        .removeClass('text-success text-warning text-danger')
        .addClass('text-primary');

      // 显示/隐藏按钮
      $('#start-registration').hide();
      $('#stop-registration').show();
      $('#registration-details').show();
      break;

    case 'stopped':
    default:
      statusBadge
        .removeClass('bg-primary bg-warning bg-danger')
        .addClass('bg-success');
      statusBadge.text('空闲中');
      taskStatusText.text(
        statusData.status_message || '系统空闲中，可以开始新任务'
      );
      taskIcon
        .removeClass('fa-spinner fa-spin fa-pause-circle fa-times-circle')
        .addClass('fa-check-circle');
      taskIcon
        .removeClass('text-primary text-warning text-danger')
        .addClass('text-success');

      // 显示/隐藏按钮
      $('#start-registration').show();
      $('#stop-registration').hide();
      $('#registration-details').hide();
      break;
  }
}

// 绑定排序事件
function bindSortEvents() {
  // 字段排序变化
  $('#sort-field').change(function () {
    currentSortField = $(this).val();
    loadAccounts(
      1,
      itemsPerPage,
      $('#search-input').val(),
      currentSortField,
      currentSortOrder
    );
  });

  // 排序方向变化
  $('#sort-order').change(function () {
    currentSortOrder = $(this).val();
    loadAccounts(
      1,
      itemsPerPage,
      $('#search-input').val(),
      currentSortField,
      currentSortOrder
    );
  });
}

// 修改表头排序配置，移除ID相关设置
function addTableHeaderSorting() {
  // 可排序的列 - 移除ID相关配置
  const sortableColumns = {
    'th-email': 'email',
    'th-date': 'created_at',
    'th-usage': 'usage_limit',
  };

  // 为表头添加排序类和点击事件
  Object.keys(sortableColumns).forEach((thId) => {
    const $th = $(`#${thId}`);
    $th.addClass('sortable');

    // 设置初始排序指示
    if (sortableColumns[thId] === currentSortField) {
      $th.addClass(currentSortOrder);
    }

    $th.click(function () {
      const field = sortableColumns[thId];

      // 如果点击当前排序列，切换排序方向
      if (field === currentSortField) {
        currentSortOrder = currentSortOrder === 'asc' ? 'desc' : 'asc';
      } else {
        // 否则，切换排序列并设置默认为降序
        currentSortField = field;
        currentSortOrder = 'desc';
      }

      // 更新排序控件
      $('#sort-field').val(currentSortField);
      $('#sort-order').val(currentSortOrder);

      // 重新加载数据
      loadAccounts(
        1,
        itemsPerPage,
        $('#search-input').val(),
        currentSortField,
        currentSortOrder
      );
    });
  });
}

// 设置定时任务刷新
function setupTaskRefresh() {
  // 清除可能存在的旧定时器
  if (refreshTimer) {
    clearInterval(refreshTimer);
  }

  // 设置新的定时刷新
  refreshTimer = setInterval(function () {
    // 检查任务状态
    checkTaskStatus();

    // 如果在账号管理页面，刷新账号列表
    if ($('#tasks-accounts').hasClass('active')) {
      // 静默刷新，不显示loading框
      loadAccounts(
        currentPage,
        itemsPerPage,
        $('#search-input').val(),
        currentSortField,
        currentSortOrder,
        false
      );

      // 更新最后刷新时间
      updateLastRefreshTime();
    }
  }, REFRESH_INTERVAL);

  // 初始加载任务状态
  checkTaskStatus();
}

// 更新最后刷新时间的函数
function updateLastRefreshTime() {
  const now = new Date();
  const timeString =
    now.getHours().toString().padStart(2, '0') +
    ':' +
    now.getMinutes().toString().padStart(2, '0') +
    ':' +
    now.getSeconds().toString().padStart(2, '0');
  $('#last-update-time').text(timeString);
}

// 检查任务状态
function checkTaskStatus() {
  fetch('/registration/status')
    .then((response) => response.json())
    .then((data) => {
      // 确保有账号统计数据
      updateTaskStatusDisplay(data);

      // 更新任务运行时间和下次运行时间
      let registration_details = data.registration_details;
      if (registration_details.last_run) {
        $('#last-run').text(formatDateTime(data.registration_details.last_run));
      }

      if (data.registration_details.next_run) {
        const nextRunTime = new Date(registration_details.next_run * 1000);
        const now = new Date();
        const timeLeft = Math.max(0, Math.floor((nextRunTime - now) / 1000));

        if (timeLeft > 0) {
          $('#next-run').text(
            `${formatDateTime(
              registration_details.next_run * 1000
            )} (还有${formatTimeLeft(timeLeft)})`
          );
        } else {
          $('#next-run').text(
            `${formatDateTime(registration_details.next_run * 1000)}`
          );
        }
      } else {
        $('#next-run').text('未排程');
      }

      // 更新注册进度和消息
      if (registration_details.registration_progress) {
        $('#registration-progress').text(
          registration_details.registration_progress
        );
      }

      if (registration_details.registration_message) {
        $('#registration-message').text(
          registration_details.registration_message
        );
      }
    })
    .catch((error) => {
      console.error('获取任务状态出错:', error);
    });
}

// 格式化日期时间
function formatDateTime(timestamp) {
  const date = new Date(timestamp);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

// 格式化剩余时间
function formatTimeLeft(seconds) {
  if (seconds < 60) {
    return `${seconds}秒`;
  } else if (seconds < 3600) {
    return `${Math.floor(seconds / 60)}分${seconds % 60}秒`;
  } else {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}小时${minutes}分`;
  }
}

// 添加重置机器ID函数
function resetMachineId() {
  showLoading();

  $.ajax({
    url: '/reset-machine',
    method: 'GET',
    success: function (response) {
      hideLoading();
      if (response.success) {
        showAlert('success', '成功重置机器ID。' + (response.message || ''));

        // 询问是否需要重启服务以应用更改
        setTimeout(function () {
          showConfirmDialog(
            '重启服务',
            '机器ID已重置，建议重启服务以确保更改生效。是否立即重启？',
            function () {
              restartService();
            }
          );
        }, 1000);
      } else {
        showAlert(
          'danger',
          '重置机器ID失败: ' + (response.message || '未知错误')
        );
      }
    },
    error: function (xhr) {
      hideLoading();
      showAlert(
        'danger',
        '重置机器ID失败: ' +
          (xhr.responseJSON?.message || xhr.statusText || '未知错误')
      );
    },
  });
}

// 导出账号函数
function exportAccounts() {
  showLoading();

  // 直接使用浏览器下载功能
  const downloadLink = document.createElement('a');
  downloadLink.href = '/accounts/export';
  downloadLink.download = 'cursor_accounts.json';
  document.body.appendChild(downloadLink);
  downloadLink.click();
  document.body.removeChild(downloadLink);

  setTimeout(() => {
    hideLoading();
    showAlert('success', '账号导出请求已发送，文件将自动下载');
  }, 1000);
}

// 导入账号函数
function importAccounts(file) {
  showLoading();

  const formData = new FormData();
  formData.append('file', file);

  // 发送导入请求
  $.ajax({
    url: '/accounts/import',
    method: 'POST',
    data: formData,
    processData: false,
    contentType: false,
    success: function (response) {
      hideLoading();
      if (response.success) {
        showAlert('success', response.message);

        // 刷新账号列表
        loadAccounts(1, itemsPerPage);
      } else {
        showAlert('danger', '导入账号失败: ' + response.message);
      }
    },
    error: function (xhr) {
      hideLoading();
      showAlert(
        'danger',
        '导入账号失败: ' + (xhr.responseJSON?.detail || xhr.statusText)
      );
    },
  });
}

// 获取账号使用记录
function getAccountUsageRecords(email, id) {
  showLoading();

  // 设置模态框中的账号邮箱
  $('#recordEmail').text(email);

  // 清空记录列表
  $('#usageRecordBody').empty();

  fetch(`/account/${id}/usage-records`)
    .then((response) => response.json())
    .then((data) => {
      hideLoading();

      if (data.success) {
        const records = data.records;

        if (records && records.length > 0) {
          // 隐藏无记录提示
          $('#no-records').hide();

          // 显示记录
          records.forEach((record) => {
            const row = `
                            <tr>
                                <td>${formatDateTime(record.created_at)}</td>
                                <td>${record.ip || '-'}</td>
                                <td class="small text-truncate" style="max-width: 300px;" title="${
                                  record.user_agent || ''
                                }">
                                    ${record.user_agent || '-'}
                                </td>
                            </tr>
                        `;
            $('#usageRecordBody').append(row);
          });
        } else {
          // 显示无记录提示
          $('#usageRecordBody').empty();
          $('#no-records').show();
        }

        // 显示模态框
        new bootstrap.Modal(document.getElementById('usageRecordModal')).show();
      } else {
        showAlert(`获取使用记录失败: ${data.message || '未知错误'}`, 'danger');
      }
    })
    .catch((error) => {
      console.error('获取使用记录时发生错误:', error);
      hideLoading();
      showAlert('获取使用记录失败，请稍后重试', 'danger');
    });
}

// 使用自定义邮箱注册
function registerWithCustomEmail() {
  const email = $('#custom-email').val().trim();
  if (!email) {
    showCustomRegistrationStatus('请输入邮箱地址', 'danger');
    return;
  }

  // 验证邮箱格式
  if (!validateEmail(email)) {
    showCustomRegistrationStatus('邮箱格式不正确', 'danger');
    return;
  }

  showCustomRegistrationStatus('注册中，请稍候...', 'info');
  $('#custom-registration').prop('disabled', true);

  // 设置全局标记，指示当前是自定义邮箱注册场景
  window.customEmailRegistration = true;

  // 启动验证码检查前清除任何可能的提示
  $('#verification-tip-alert').hide();
  // 短暂延迟后再启动验证码检查，确保UI已更新
  setTimeout(() => {
    // 启动验证码检查
    startVerificationCodeCheck();
  }, 500);

  // 调用API
  $.ajax({
    url: '/registration/custom',
    method: 'POST',
    contentType: 'application/json',
    data: JSON.stringify({ email: email }),
    success: function (response) {
      if (response.success) {
        showCustomRegistrationStatus('注册成功！', 'success');
        // 重置表单
        $('#custom-email').val('');
        // 刷新账号列表
        setTimeout(function () {
          loadAccounts(1, itemsPerPage);
          // 注册成功后停止验证码检查
          stopVerificationCodeCheck();
          // 清除自定义邮箱注册标记
          window.customEmailRegistration = false;
        }, 2000);
      } else {
        showCustomRegistrationStatus('注册失败: ' + response.message, 'danger');
        // 注册失败后停止验证码检查
        stopVerificationCodeCheck();
        // 清除自定义邮箱注册标记
        window.customEmailRegistration = false;
      }
      $('#custom-registration').prop('disabled', false);
    },
    error: function (xhr) {
      let message = '注册失败';
      try {
        const response = JSON.parse(xhr.responseText);
        message = response.message || '未知错误';
      } catch (e) {
        message = xhr.statusText || '服务器错误';
      }
      showCustomRegistrationStatus('注册失败: ' + message, 'danger');
      $('#custom-registration').prop('disabled', false);
      // 注册错误后停止验证码检查
      stopVerificationCodeCheck();
      // 清除自定义邮箱注册标记
      window.customEmailRegistration = false;
    },
  });
}

// 显示自定义注册状态
function showCustomRegistrationStatus(message, type) {
  const statusDiv = $('#custom-registration-status');
  const messageSpan = $('#custom-registration-message');

  statusDiv
    .removeClass('alert-info alert-success alert-danger')
    .addClass('alert-' + type)
    .show();

  messageSpan.text(message);

  if (type === 'success') {
    setTimeout(function () {
      statusDiv.hide();
    }, 5000);
  }
}

// 验证邮箱格式
function validateEmail(email) {
  const re =
    /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
  return re.test(String(email).toLowerCase());
}

// 绑定模态框内按钮事件
function bindModalEvents() {
  // 使用Token按钮 - 使用节流处理
  $('#useTokenBtn')
    .off('click')
    .on(
      'click',
      throttle(function () {
        // 直接从DOM元素获取属性
        const accountId =
          document
            .getElementById('useTokenBtn')
            .getAttribute('data-account-id') || '';

        if (!accountId) {
          showAlert('无法获取账号ID，请刷新页面后重试', 'danger');
          return;
        }

        showLoading('正在使用Token...');
        fetch(`/account/use-token/${accountId}`, {
          method: 'POST',
        })
          .then((res) => {
            if (!res.ok) {
              throw new Error(`服务器返回状态码: ${res.status}`);
            }
            return res.json();
          })
          .then((data) => {
            hideLoading();
            if (data.success) {
              showAlert(data.message, 'success');
              $('#tokenViewModal').modal('hide');
              cleanupModalBackdrops();
              setTimeout(() => fetchAccounts(), 1000);
            } else {
              showAlert(
                `使用Token失败: ${data.message || '未知错误'}`,
                'danger'
              );
            }
          })
          .catch((error) => {
            console.error('使用Token时发生错误:', error);
            hideLoading();
            showAlert(`使用Token失败: ${error.message}`, 'danger');
          });
      }, 1000)
    );

  // 监听模态框隐藏事件
  $('.modal')
    .off('hidden.bs.modal')
    .on('hidden.bs.modal', function () {
      // 延迟调用清理，避免与Bootstrap自身的处理冲突
      setTimeout(() => cleanupModalBackdrops(), 50);
    });
}

// 验证码请求检查
let verificationCheckTimer;

function startVerificationCodeCheck() {
  // 清除可能存在的计时器
  if (verificationCheckTimer) {
    clearInterval(verificationCheckTimer);
  }

  // 获取当前操作模式 - 检查是否在任务注册页面或自定义邮箱注册
  const isTaskRegistration =
    $('#task-status').length > 0 &&
    $('#task-status').is(':visible') &&
    !window.customEmailRegistration;
  const isCustomEmailRegistration = window.customEmailRegistration === true;

  // 根据不同场景显示不同的提示文案
  if (isTaskRegistration) {
    // 任务注册场景
    $('#verification-tip-content').text(
      '在任务注册过程中，如果自动获取验证码失败，系统将自动转为手动输入模式，请留意弹窗提示并及时输入验证码。'
    );
  } else if (isCustomEmailRegistration) {
    // 自定义邮箱注册场景
    $('#verification-tip-content').text(
      '使用自定义邮箱注册时，需要手动输入验证码，请检查您的邮箱并在弹窗中及时输入验证码。'
    );
  } else {
    // 默认场景
    $('#verification-tip-content').text(
      '在注册过程中，系统将请求邮箱验证码。如需手动输入验证码，请留意弹窗提示并及时输入。'
    );
  }

  // 显示验证码提示框
  $('#verification-tip-alert').show();

  // 每5秒检查一次是否有等待验证码输入的请求
  verificationCheckTimer = setInterval(checkPendingVerification, 5000);
}

function stopVerificationCodeCheck() {
  if (verificationCheckTimer) {
    clearInterval(verificationCheckTimer);
    verificationCheckTimer = null;

    // 隐藏验证码提示框
    $('#verification-tip-alert').hide();

    // 清除自定义邮箱注册标记
    window.customEmailRegistration = false;

    // 调用后端接口清理所有待处理的验证码请求
    fetch('/verification/clear')
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          console.log('已清理待处理的验证码请求:', data.message);

          // 如果当前有打开的验证码输入弹窗，关闭它
          if ($('#codeInputModal').hasClass('show')) {
            const modalElement = document.getElementById('codeInputModal');
            const modalInstance = bootstrap.Modal.getInstance(modalElement);
            if (modalInstance) {
              modalInstance.hide();
              setTimeout(() => cleanupModalBackdrops(), 300);
            }
          }
        }
      })
      .catch((error) => {
        console.error('清理验证码请求失败:', error);
      });
  }
}

function checkPendingVerification() {
  // 如果验证码模态框已经打开，不要重复检查和打开
  if ($('#codeInputModal').hasClass('show')) {
    return;
  }

  fetch('/verification/pending')
    .then((response) => {
      if (!response.ok) {
        throw new Error(`服务器返回状态码: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => {
      if (data.success && data.data && data.data.length > 0) {
        // 检查是否有失败的验证码请求
        const failedRequest = data.data.find((req) => req.status === 'failed');
        if (failedRequest) {
          // 显示验证失败信息并更新内容，但不停止验证码检查，因为系统会转为手动模式
          showAlert(
            `自动获取验证码失败: ${
              failedRequest.message || '请检查邮箱设置'
            }。系统已自动转为手动输入模式，请等待验证码输入弹窗。`,
            'warning'
          );
          return;
        }

        // 处理正常的验证码请求
        const pendingRequest = data.data[0]; // 取第一个请求

        // 确保没有其他模态框正在显示
        if (!$('.modal.show').length) {
          showVerificationModal(pendingRequest);
        } else {
          // 延迟500ms后重试
          setTimeout(checkPendingVerification, 500);
        }
      }
    })
    .catch((error) => {
      console.error('检查验证码请求失败:', error);
      // 错误后延长重试时间
      clearTimeout(verificationCheckTimer);
      verificationCheckTimer = setTimeout(checkPendingVerification, 10000);
    });
}

function showVerificationModal(pendingRequest) {
  try {
    // 检查pendingRequest是否有效
    if (!pendingRequest || !pendingRequest.email || !pendingRequest.id) {
      console.error('无效的验证请求:', pendingRequest);
      return;
    }

    // 设置邮箱显示
    $('#verificationEmailDisplay').text(pendingRequest.email);
    // 设置请求ID
    $('#pendingEmailId').val(pendingRequest.id);
    // 清空验证码输入框
    $('#verificationCode').val('');

    // 判断是否是自动失败后的手动输入请求
    const isAutoFailureCase =
      pendingRequest.hasOwnProperty('auto_failure') &&
      pendingRequest.auto_failure === true;

    // 判断是否是任务注册场景或自定义邮箱注册场景
    const isTaskRegistration =
      $('#task-status').length > 0 &&
      $('#task-status').is(':visible') &&
      !window.customEmailRegistration;
    const isCustomEmailRegistration =
      window.customEmailRegistration === true ||
      (pendingRequest.email.includes('@') &&
        !pendingRequest.email.includes('tempmail.plus') &&
        !pendingRequest.email.includes('zmail.plus'));

    // 设置模态框标题和内容，根据场景提供不同提示
    if (isTaskRegistration && isAutoFailureCase) {
      // 任务注册场景 - 自动获取失败后的手动输入
      $('#codeInputModalLabel').text('任务注册 - 手动输入验证码');
      $('#verification-message').html(
        '<div class="alert alert-warning mb-3">自动获取验证码失败，请手动输入验证码以继续注册流程。</div>'
      );
      $('#verification-code-hint').text(
        '请检查邮箱中的验证邮件，通常验证码为6位数字，位于邮件正文中。'
      );
    } else if (isTaskRegistration) {
      // 任务注册场景 - 普通手动输入
      $('#codeInputModalLabel').text('任务注册 - 输入验证码');
      $('#verification-message').html('');
      $('#verification-code-hint').text(
        '通常验证码为6位数字，在邮件正文中可以找到。'
      );
    } else if (isCustomEmailRegistration) {
      // 自定义邮箱注册场景
      $('#codeInputModalLabel').text('自定义邮箱注册 - 输入验证码');
      $('#verification-message').html(
        '<div class="alert alert-info mb-3">请查看您的邮箱，输入收到的验证码完成注册。</div>'
      );
      $('#verification-code-hint').text(
        '请检查您的邮箱收件箱及垃圾邮件文件夹，验证码通常为6位数字。'
      );
    } else {
      // 默认场景
      $('#codeInputModalLabel').text('请输入验证码');
      $('#verification-message').html('');
      $('#verification-code-hint').text('通常验证码为6位数字，在邮件正文中');
    }

    // 显示模态框前先清理可能存在的背景
    cleanupModalBackdrops();

    // 显示模态框
    const codeModal = new bootstrap.Modal(
      document.getElementById('codeInputModal')
    );
    codeModal.show();

    // 聚焦到验证码输入框
    setTimeout(() => {
      $('#verificationCode').focus();
    }, 500);

    // 显示提示
    showAlert(`请为邮箱 ${pendingRequest.email} 输入验证码`, 'info');
  } catch (error) {
    console.error('显示验证码模态框时发生错误:', error);
  }
}

// 绑定验证码相关事件
function bindVerificationEvents() {
  // 提交验证码按钮
  $('#submitCodeBtn').click(function () {
    submitVerificationCode();
  });

  // 验证码输入框回车事件
  $('#verificationCode').keypress(function (e) {
    if (e.which === 13) {
      submitVerificationCode();
    }
  });

  // 模态框关闭事件
  $('#codeInputModal').on('hidden.bs.modal', function () {
    // 清空数据
    $('#verificationEmailDisplay').text('');
    $('#pendingEmailId').val('');
    $('#verificationCode').val('');

    // 清理背景
    cleanupModalBackdrops();
  });
}

// 清理Bootstrap模态框背景遮罩和相关样式 - 增强可靠性
function cleanupModalBackdrops() {
  try {
    // 立即执行一次基本清理
    const immediateBackdrops = $('.modal-backdrop');

    // 如果找到超过1个背景，立即移除多余的
    if (immediateBackdrops.length > 1) {
      // 保留第一个，移除其他
      immediateBackdrops.slice(1).remove();
    }

    // 再等待Bootstrap模态框动画完成后彻底清理
    setTimeout(() => {
      try {
        // 检查是否还有显示中的模态框
        const visibleModals = $('.modal.show').length;

        // 只有在没有显示中的模态框时才移除所有背景
        if (visibleModals === 0) {
          // 获取所有模态框背景
          const backdrops = $('.modal-backdrop');
          if (backdrops.length > 0) {
            backdrops.remove();

            // 重置body的样式
            $('body').removeClass('modal-open');
            $('body').css('overflow', '');
            $('body').css('padding-right', '');

            // 额外确保任何可能的内联样式都被移除
            $('body').attr('style', '');
          }
        } else {
          // 即使有模态框显示，也确保只有一个背景
          const backdrops = $('.modal-backdrop');
          if (backdrops.length > 1) {
            backdrops.slice(1).remove();
          }
        }

        // 确保文档滚动正常
        $(document).off('scroll.bs.modal');
      } catch (error) {
        console.error('延迟清理背景时发生错误:', error);
      }
    }, 300); // 延迟确保在Bootstrap的模态框关闭动画完成后执行
  } catch (error) {
    console.error('清理模态框背景时发生错误:', error);
    // 尝试最基本的清理
    try {
      $('.modal-backdrop').remove();
      $('body')
        .removeClass('modal-open')
        .css('overflow', '')
        .css('padding-right', '');
    } catch (e) {
      console.error('紧急清理模态框背景时发生错误:', e);
    }
  }
}

// 修改submitVerificationCode函数使用通用清理方法
function submitVerificationCode() {
  const code = $('#verificationCode').val().trim();
  const id = $('#pendingEmailId').val();

  if (!code) {
    showAlert('请输入验证码', 'warning');
    return;
  }

  if (!id) {
    showAlert('验证请求ID无效', 'danger');
    return;
  }

  // 显示加载状态并防止重复提交
  if ($('#submitCodeBtn').prop('disabled')) {
    return;
  }

  $('#submitCodeBtn')
    .prop('disabled', true)
    .html('<i class="fas fa-spinner fa-spin me-1"></i> 提交中...');

  // 提交验证码
  fetch('/verification/submit', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      id: id,
      code: code,
    }),
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`服务器返回状态码: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => {
      if (data.success) {
        showAlert(`验证码已成功提交 (${code})`, 'success');

        // 先记录模态框实例以便后续使用
        const modalElement = document.getElementById('codeInputModal');
        const modalInstance = bootstrap.Modal.getInstance(modalElement);

        if (modalInstance) {
          // 清空数据，防止重复提交
          $('#verificationEmailDisplay').text('');
          $('#pendingEmailId').val('');
          $('#verificationCode').val('');

          // 关闭模态框并清理背景
          modalInstance.hide();
          setTimeout(() => cleanupModalBackdrops(), 300);

          // 如果验证成功，可以重新加载账号列表
          showAlert('等待账号注册完成...', 'info');
          setTimeout(fetchAccounts, 10000); // 增加等待时间到10秒

          // 任务可能已经完成，检查是否需要隐藏提示
          fetch('/registration/status')
            .then((res) => res.json())
            .then((status) => {
              if (status.task_status === 'stopped') {
                $('#verification-tip-alert').hide();
                stopVerificationCodeCheck();
              }
            })
            .catch((error) => console.error('获取任务状态失败:', error));
        }
      } else {
        showAlert(`提交验证码失败: ${data.message || '未知错误'}`, 'danger');
      }
    })
    .catch((error) => {
      console.error('提交验证码失败:', error);
      showAlert(`提交验证码失败: ${error.message}`, 'danger');
    })
    .finally(() => {
      // 恢复按钮状态，延迟恢复防止快速点击
      setTimeout(() => {
        $('#submitCodeBtn').prop('disabled', false).html('提交验证码');
      }, 1000);
    });
}

// 打开删除确认模态框
function confirmDeleteAccount(accountId) {
  $('#deleteAccountId').val(accountId);
  const modal = new bootstrap.Modal(
    document.getElementById('deleteConfirmModal')
  );
  modal.show();
}

// 获取账号列表
function fetchAccounts() {
  showLoading('加载账号数据中...');

  // 构建查询参数
  const queryParams = new URLSearchParams({
    page: currentPage,
    per_page: itemsPerPage,
    sort_field: currentSortField,
    sort_order: currentSortOrder,
  });

  // 如果有搜索词，添加到查询参数
  const searchTerm = $('#search-input').val().trim();
  if (searchTerm) {
    queryParams.append('search', searchTerm);
  }

  // 发起请求
  fetch(`/accounts?${queryParams.toString()}`)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`服务器返回状态码: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => {
      if (data.success) {
        // 保存账号数据
        accounts = data.data || [];

        // 关闭"等待账号注册完成..."的提示
        $('.alert-info:contains("等待账号注册完成")').alert('close');

        // 直接更新账号表格，不需要额外的过滤和排序
        updateAccountsTable(accounts);

        // 更新分页信息
        updatePagination(data.pagination.page, data.pagination.total_pages);
        $('#total-accounts').text(data.pagination.total_count);
      } else {
        showAlert(
          '加载账号失败: ' + (data.message || '服务器返回错误'),
          'danger'
        );
        console.error('加载账号数据失败:', data);
      }
    })
    .catch((error) => {
      console.error('获取账号列表时发生错误:', error);
      showAlert('加载账号失败: ' + error.message, 'danger');

      // 如果是网络错误，显示更详细的提示
      if (
        error.name === 'TypeError' &&
        error.message.includes('Failed to fetch')
      ) {
        showAlert('网络连接错误，请检查服务是否正常运行', 'danger', true);
      }
    })
    .finally(() => {
      hideLoading();
    });
}
