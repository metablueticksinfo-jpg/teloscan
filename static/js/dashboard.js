class Dashboard {
  constructor() {
    this.init();
    this.setupEventListeners();
    this.startStatsUpdater();
    this.startLogUpdater();
    this.loadInitialAdvancedSections();
  }

  init() {
    this.currentSection = 'dashboard';
    this.isScrapingActive = false;
    this.statsUpdateInterval = null;
    this.logUpdateInterval = null;
    this.filtersInitialized = false;

    this.resultsPage = 1;
    this.resultsPerPage = 50;
    this.resultsTotalPages = 1;
    this.resultsLoading = false;

    this.sidebarMiniKey = 'dashboard_sidebar_mini';
  }

  setupEventListeners() {
    document.querySelectorAll('.nav-link').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const section = link.dataset.section;
        this.showSection(section);

        if (window.innerWidth <= 991) {
          this.toggleSidebar(false);
        }
      });
    });

    const toggleBtn = document.getElementById('sidebarToggle');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => this.toggleSidebar());
    }

    const miniToggleBtn = document.getElementById('sidebarMiniToggle');
    if (miniToggleBtn) {
      miniToggleBtn.addEventListener('click', () => this.toggleSidebarMini());
    }

    this.bindClick('logoutBtn', () => this.logout());
    this.bindClick('getSecUidBtn', () => this.getUserId());
    this.bindClick('startScraperBtn', () => this.startScraper());
    this.bindClick('stopScraperBtn', () => this.stopScraper());

    this.bindClick('clearLogsBtn', () => this.clearLogs());
    this.bindClick('downloadLogsBtn', () => this.downloadLogs());

    this.bindClick('testSmtpBtn', () => this.testSmtp());
    this.bindClick('sendEmailsBtn', () => this.sendEmails());

    this.bindClick('downloadAllEmailsTxt', () => this.downloadEmails('txt', 'all'));
    this.bindClick('downloadShopEmailsTxt', () => this.downloadEmails('txt', 'shop'));
    this.bindClick('downloadNormalEmailsTxt', () => this.downloadEmails('txt', 'normal'));
    this.bindClick('downloadAllEmailsCsv', () => this.downloadEmails('csv', 'all'));

    this.bindClick('exportResultsXlsxBtn', () => this.exportResults('xlsx'));
    this.bindClick('exportResultsCsvBtn', () => this.exportResults('csv'));
    this.bindClick('exportResultsJsonBtn', () => this.exportResults('json'));

    this.bindClick('refreshRegionAnalysisBtn', () => this.loadRegionAnalysis());
    this.bindClick('refreshQueueBtn', () => this.loadQueueStatus());
    this.bindClick('refreshChartsBtn', () => this.loadChartData());
    this.bindClick('refreshResultsBtn', () => {
      this.resultsPage = 1;
      this.loadResults();
    });

    this.bindClick('resultsPrevBtn', () => this.changeResultsPage(-1));
    this.bindClick('resultsNextBtn', () => this.changeResultsPage(1));

    this.bindClick('saveAppearanceBtn', () => this.saveAppearanceSettings());

    /* Yeni: filtrelenmiş sonuçları TXT indir */
    this.bindClick('downloadFilteredResultsTxtBtn', () => this.downloadFilteredResultsTxt());

    /* Preset Buttons */
    this.bindClick('presetRegionUSBtn', () => this.applyResultsPreset({ region: 'US' }));
    this.bindClick('presetRegionTRBtn', () => this.applyResultsPreset({ region: 'TR' }));
    this.bindClick('presetVerifiedBtn', () => this.applyResultsPreset({ verifiedOnly: true }));
    this.bindClick('presetShopBtn', () => this.applyResultsPreset({ shopType: 'shop' }));
    this.bindClick('presetEmailBtn', () => this.applyResultsPreset({ emailOnly: true }));
    this.bindClick('presetClearBtn', () => this.clearResultsFilters());

    const resultsPerPage = document.getElementById('resultsPerPage');
    if (resultsPerPage) {
      resultsPerPage.addEventListener('change', () => {
        this.resultsPerPage = parseInt(resultsPerPage.value, 10) || 50;
        this.resultsPage = 1;
        this.loadResults();
      });
    }

    const resultsSearch = document.getElementById('resultsSearch');
    if (resultsSearch) {
      resultsSearch.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          this.resultsPage = 1;
          this.loadResults();
        }
      });
    }

    const resultsRegionFilter = document.getElementById('resultsRegionFilter');
    if (resultsRegionFilter) {
      resultsRegionFilter.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          this.resultsPage = 1;
          this.loadResults();
        }
      });
    }

    const resultsShopType = document.getElementById('resultsShopType');
    if (resultsShopType) {
      resultsShopType.addEventListener('change', () => {
        this.resultsPage = 1;
        this.loadResults();
      });
    }

    const resultsVerifiedOnly = document.getElementById('resultsVerifiedOnly');
    if (resultsVerifiedOnly) {
      resultsVerifiedOnly.addEventListener('change', () => {
        this.resultsPage = 1;
        this.loadResults();
      });
    }

    const resultsEmailOnly = document.getElementById('resultsEmailOnly');
    if (resultsEmailOnly) {
      resultsEmailOnly.addEventListener('change', () => {
        this.resultsPage = 1;
        this.loadResults();
      });
    }

    const exportRegionFilter = document.getElementById('exportRegionFilter');
    if (exportRegionFilter) {
      exportRegionFilter.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') this.exportResults('xlsx');
      });
    }

    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
      themeToggle.addEventListener('change', () => this.previewAppearanceSettings());
    }

    const accentColorSelect = document.getElementById('accentColorSelect');
    if (accentColorSelect) {
      accentColorSelect.addEventListener('change', () => this.previewAppearanceSettings());
    }

    if (window.userRole === 'admin') {
      this.bindClick('addUserBtn', () => this.addUser());
      this.bindClick('blockIpBtn', () => this.blockIp());

      this.bindClick('refreshUsersBtn', () => this.loadUsers());
      this.bindClick('refreshAdminOverviewBtn', () => this.loadAdminOverview());

      this.bindClick('freezeUserBtn', () => this.freezeUser());
      this.bindClick('unfreezeUserBtn', () => this.unfreezeUser());
      this.bindClick('resetUserLimitsBtn', () => this.resetUserLimits());
      this.bindClick('savePackageBtn', () => this.savePackageSettings());

      this.loadUsers();
      this.loadBlockedIps();
      this.loadAdminOverview();
      this.loadPackageSummary();
    }

    this.loadSidebarMiniState();
  }

  bindClick(id, handler) {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', handler);
  }

  async apiGet(url) {
    const response = await fetch(url, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    let data = {};
    try {
      data = await response.json();
    } catch (_) {
      data = {};
    }

    return { response, data };
  }

  async apiPost(url, payload = {}) {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    let data = {};
    try {
      data = await response.json();
    } catch (_) {
      data = {};
    }

    return { response, data };
  }

  loadInitialAdvancedSections() {
    this.loadRegionAnalysis();
    this.loadQueueStatus();
    this.loadChartData();
    this.loadResults();
    this.loadAppearanceSettings();

    if (window.userRole === 'admin') {
      this.loadAdminOverview();
      this.loadPackageSummary();
    }
  }

  showSection(sectionName) {
    document.querySelectorAll('.nav-link').forEach(link => {
      link.classList.remove('active');
    });

    const activeLink = document.querySelector(`[data-section="${sectionName}"]`);
    if (activeLink) activeLink.classList.add('active');

    document.querySelectorAll('.content-section').forEach(section => {
      section.classList.remove('active');
    });

    const activeSection = document.getElementById(`${sectionName}-section`);
    if (activeSection) activeSection.classList.add('active');

    this.currentSection = sectionName;

    if (sectionName === 'region-analysis') this.loadRegionAnalysis();
    if (sectionName === 'queue-management') this.loadQueueStatus();
    if (sectionName === 'charts') this.loadChartData();
    if (sectionName === 'results') this.loadResults();
    if (sectionName === 'admin-overview') this.loadAdminOverview();
    if (sectionName === 'admin-packages') this.loadPackageSummary();
    if (sectionName === 'users') this.loadUsers();
    if (sectionName === 'ip-management') this.loadBlockedIps();
  }

  toggleSidebar(forceState = null) {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;

    if (forceState === true) {
      sidebar.classList.add('show');
      return;
    }

    if (forceState === false) {
      sidebar.classList.remove('show');
      return;
    }

    sidebar.classList.toggle('show');
  }

  toggleSidebarMini() {
    if (window.innerWidth <= 991) return;

    const willBeMini = !document.body.classList.contains('sidebar-mini');
    document.body.classList.toggle('sidebar-mini', willBeMini);
    localStorage.setItem(this.sidebarMiniKey, willBeMini ? '1' : '0');
  }

  loadSidebarMiniState() {
    if (window.innerWidth <= 991) {
      document.body.classList.remove('sidebar-mini');
      return;
    }

    const saved = localStorage.getItem(this.sidebarMiniKey);
    document.body.classList.toggle('sidebar-mini', saved === '1');
  }

  async logout() {
    try {
      const { response } = await this.apiPost('/logout');
      if (response.ok) window.location.href = '/';
    } catch (error) {
      console.error('Logout error:', error);
    }
  }

  getUserIdField() {
    return document.getElementById('userId') || document.getElementById('secUid');
  }

  getSecUidField() {
    return document.getElementById('secUid');
  }

  getRegionFilterField() {
    return document.getElementById('regionFilter');
  }

  getResultsRegionField() {
    return document.getElementById('resultsRegionFilter');
  }

  setResolvedIds(data) {
    const userIdField = document.getElementById('userId');
    const secUidField = document.getElementById('secUid');

    if (userIdField && data.userId) userIdField.value = data.userId;
    if (secUidField && data.userId) secUidField.value = data.userId;

    if (secUidField && data.secUid) secUidField.dataset.realSecuid = data.secUid;
    if (userIdField && data.secUid) userIdField.dataset.realSecuid = data.secUid;
  }

  applyFiltersToUI(filters = {}) {
    if (document.getElementById('minFollowers')) {
      document.getElementById('minFollowers').value = filters.min_followers ?? 0;
    }

    if (document.getElementById('maxFollowers')) {
      document.getElementById('maxFollowers').value = filters.max_followers ?? 9999999;
    }

    if (document.getElementById('verifiedFilter') && filters.verified_filter) {
      document.getElementById('verifiedFilter').value = filters.verified_filter;
    }

    if (document.getElementById('emailFilter') && filters.email_filter) {
      document.getElementById('emailFilter').value = filters.email_filter;
    }

    if (document.getElementById('ttsellerFilter') && filters.ttseller_filter) {
      document.getElementById('ttsellerFilter').value = filters.ttseller_filter;
    }

    const regionField = this.getRegionFilterField();
    if (regionField) {
      const regions = Array.isArray(filters.region_filter) ? filters.region_filter.join(',') : '';
      regionField.value = regions;
    }
  }

  /* =========================
     RESULTS PRESETS
  ========================= */

  applyResultsPreset({
    region = null,
    verifiedOnly = null,
    emailOnly = null,
    shopType = null
  } = {}) {
    const search = document.getElementById('resultsSearch');
    const regionField = document.getElementById('resultsRegionFilter');
    const verifiedField = document.getElementById('resultsVerifiedOnly');
    const emailField = document.getElementById('resultsEmailOnly');
    const shopField = document.getElementById('resultsShopType');

    if (search) search.value = '';

    if (regionField && region !== null) {
      regionField.value = region;
    }

    if (verifiedField && verifiedOnly !== null) {
      verifiedField.checked = !!verifiedOnly;
    }

    if (emailField && emailOnly !== null) {
      emailField.checked = !!emailOnly;
    }

    if (shopField && shopType !== null) {
      shopField.value = shopType;
    }

    this.resultsPage = 1;
    this.loadResults();
  }

  clearResultsFilters() {
    const search = document.getElementById('resultsSearch');
    const regionField = document.getElementById('resultsRegionFilter');
    const verifiedField = document.getElementById('resultsVerifiedOnly');
    const emailField = document.getElementById('resultsEmailOnly');
    const shopField = document.getElementById('resultsShopType');

    if (search) search.value = '';
    if (regionField) regionField.value = '';
    if (verifiedField) verifiedField.checked = false;
    if (emailField) emailField.checked = false;
    if (shopField) shopField.value = 'all';

    this.resultsPage = 1;
    this.loadResults();
  }

  /* =========================
     SCRAPER
  ========================= */

  async getUserId() {
    const usernameInput = document.getElementById('tiktokUsername');
    const username = usernameInput ? usernameInput.value.trim() : '';

    if (!username) {
      this.showAlert('Lütfen kullanıcı adı girin.', 'warning');
      return;
    }

    this.showLoading(true);

    try {
      const { data } = await this.apiPost('/get_secu_id', { username });

      if (data.userId) {
        this.setResolvedIds(data);
        this.showAlert('UserID başarıyla bulundu!', 'success');
      } else {
        this.showAlert(data.error || 'UserID bulunamadı.', 'error');
      }
    } catch (error) {
      this.showAlert('Bağlantı hatası.', 'error');
    } finally {
      this.showLoading(false);
    }
  }

  async getSecUid() {
    return this.getUserId();
  }

  async startScraper() {
    const userIdField = this.getUserIdField();
    const userId = userIdField ? userIdField.value.trim() : '';
    const regionField = this.getRegionFilterField();
    const regionFilter = regionField ? regionField.value.trim() : '';

    if (!userId) {
      this.showAlert('Lütfen önce UserID alın.', 'warning');
      return;
    }

    const scraperData = {
      userId,
      minFollowers: document.getElementById('minFollowers')?.value || 0,
      maxFollowers: document.getElementById('maxFollowers')?.value || 9999999,
      verifiedFilter: document.getElementById('verifiedFilter')?.value || 'any',
      emailFilter: document.getElementById('emailFilter')?.value || 'all',
      ttsellerFilter: document.getElementById('ttsellerFilter')?.value || 'any',
      regionFilter
    };

    try {
      const { response, data } = await this.apiPost('/start_scraper', scraperData);

      if (response.ok) {
        this.isScrapingActive = true;
        this.updateScraperButtons();

        if (data.filters) {
          this.applyFiltersToUI(data.filters);
          this.filtersInitialized = true;
        }

        this.showAlert('Scraper başlatıldı!', 'success');
        this.loadQueueStatus();
      } else {
        this.showAlert(data.error || 'Scraper başlatılamadı.', 'error');
      }
    } catch (error) {
      this.showAlert('Bağlantı hatası.', 'error');
    }
  }

  async stopScraper() {
    try {
      const { response } = await this.apiPost('/stop_scraper');
      if (response.ok) {
        this.isScrapingActive = false;
        this.updateScraperButtons();
        this.showAlert('Scraper durduruldu!', 'info');
        this.loadQueueStatus();
      }
    } catch (error) {
      this.showAlert('Bağlantı hatası.', 'error');
    }
  }

  updateScraperButtons() {
    const startBtn = document.getElementById('startScraperBtn');
    const stopBtn = document.getElementById('stopScraperBtn');
    const statusBadge = document.getElementById('scraperStatus');

    if (!startBtn || !stopBtn || !statusBadge) return;

    if (this.isScrapingActive) {
      startBtn.disabled = true;
      stopBtn.disabled = false;
      statusBadge.textContent = 'Çalışıyor';
      statusBadge.className = 'badge bg-success';
    } else {
      startBtn.disabled = false;
      stopBtn.disabled = true;
      statusBadge.textContent = 'Durdu';
      statusBadge.className = 'badge bg-secondary';
    }
  }

  /* =========================
     LOGS / EMAIL / EXPORT
  ========================= */

  async clearLogs() {
    if (!confirm('Tüm logları ve sonuçları temizlemek istediğinizden emin misiniz?')) return;

    try {
      const { response } = await this.apiPost('/clear_logs');

      if (response.ok) {
        const logsContainer = document.getElementById('logsContainer');
        const mailLogsContainer = document.getElementById('mailLogsContainer');
        const recentUsers = document.getElementById('recentUsers');
        const resultsTable = document.getElementById('resultsTableBody');
        const regionAnalysisBody = document.getElementById('regionAnalysisTableBody');

        if (logsContainer) {
          logsContainer.innerHTML = '<div class="text-muted text-center">Log mesajları burada görünecek...</div>';
        }
        if (mailLogsContainer) {
          mailLogsContainer.innerHTML = '<div class="text-muted text-center">E-posta logları burada görünecek...</div>';
        }
        if (recentUsers) {
          recentUsers.innerHTML = '<div class="text-muted text-center">Henüz kullanıcı eklenmedi...</div>';
        }
        if (resultsTable) {
          resultsTable.innerHTML = '<tr><td colspan="10" class="text-center text-muted">Sonuç bulunamadı</td></tr>';
        }
        if (regionAnalysisBody) {
          regionAnalysisBody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">Veri bulunamadı</td></tr>';
        }

        this.showAlert('Loglar ve sonuçlar temizlendi!', 'success');
        this.loadRegionAnalysis();
        this.loadQueueStatus();
        this.loadChartData();
        this.loadResults();
      }
    } catch (error) {
      this.showAlert('Bağlantı hatası.', 'error');
    }
  }

  downloadLogs() {
    const logsContainer = document.getElementById('logsContainer');
    if (!logsContainer) return;

    const logs = Array.from(logsContainer.querySelectorAll('.log-entry'))
      .map(entry => entry.textContent.trim())
      .join('\n');

    if (!logs || logs.length === 0) {
      this.showAlert('İndirilecek log bulunamadı.', 'warning');
      return;
    }

    const blob = new Blob([logs], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tiktok_logs_${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  async testSmtp() {
    const smtpData = {
      host: document.getElementById('smtpHost')?.value || '',
      port: document.getElementById('smtpPort')?.value || '',
      user: document.getElementById('smtpUser')?.value || '',
      pass: document.getElementById('smtpPass')?.value || ''
    };

    if (!smtpData.host || !smtpData.user || !smtpData.pass) {
      this.showAlert('Lütfen SMTP bilgilerini doldurun.', 'warning');
      return;
    }

    const testData = {
      ...smtpData,
      from: smtpData.user,
      subject: 'SMTP Test',
      html: '<h1>Test E-postası</h1><p>SMTP ayarlarınız çalışıyor!</p>',
      recipients: [{ email: smtpData.user, username: 'test' }],
      delay: 0
    };

    this.showLoading(true);

    try {
      const { data } = await this.apiPost('/send_mail', testData);

      if (data.status === 'ok') {
        this.showAlert('Test e-postası başarıyla gönderildi!', 'success');
      } else {
        this.showAlert(data.message || 'SMTP testi başarısız.', 'error');
      }
    } catch (error) {
      this.showAlert('Bağlantı hatası.', 'error');
    } finally {
      this.showLoading(false);
    }
  }

  async sendEmails() {
    const smtpData = {
      host: document.getElementById('smtpHost')?.value || '',
      port: document.getElementById('smtpPort')?.value || '',
      user: document.getElementById('smtpUser')?.value || '',
      pass: document.getElementById('smtpPass')?.value || '',
      from: document.getElementById('smtpUser')?.value || '',
      subject: document.getElementById('emailSubject')?.value || '',
      html: document.getElementById('emailContent')?.value || '',
      delay: parseInt(document.getElementById('emailDelay')?.value, 10) || 1000
    };

    if (!smtpData.host || !smtpData.user || !smtpData.pass || !smtpData.subject || !smtpData.html) {
      this.showAlert('Lütfen tüm e-posta bilgilerini doldurun.', 'warning');
      return;
    }

    try {
      const { data } = await this.apiGet('/download_emails');

      if (!data.emails || data.emails.length === 0) {
        this.showAlert('Gönderilecek e-posta bulunamadı.', 'warning');
        return;
      }

      const recipients = data.emails.map(emailStr => {
        const [username, email] = emailStr.split(':');
        return { username, email };
      });

      smtpData.recipients = recipients;

      if (!confirm(`${recipients.length} e-posta gönderilecek. Devam etmek istiyor musunuz?`)) return;

      this.showLoading(true);

      const { data: sendData } = await this.apiPost('/send_mail', smtpData);

      if (sendData.status === 'ok') {
        this.showAlert(`${sendData.count} e-posta başarıyla gönderildi!`, 'success');
      } else {
        this.showAlert(sendData.message || 'E-posta gönderimi başarısız.', 'error');
      }
    } catch (error) {
      this.showAlert('Bağlantı hatası.', 'error');
    } finally {
      this.showLoading(false);
    }
  }

  async downloadEmails(format, type = 'all') {
    try {
      const { data } = await this.apiGet(`/download_emails?type=${type}`);

      if (!data.emails || data.emails.length === 0) {
        this.showAlert('İndirilecek e-posta bulunamadı.', 'warning');
        return;
      }

      let content;
      let filename;
      let mimeType;
      const typeLabel = type === 'shop' ? 'shop_' : type === 'normal' ? 'normal_' : '';

      if (format === 'csv') {
        content = 'Username,Email\n' + data.emails.map(emailStr => {
          const [username, email] = emailStr.split(':');
          return `${username},${email}`;
        }).join('\n');
        filename = `${typeLabel}emails_${new Date().toISOString().split('T')[0]}.csv`;
        mimeType = 'text/csv';
      } else {
        content = data.emails.join('\n');
        filename = `${typeLabel}emails_${new Date().toISOString().split('T')[0]}.txt`;
        mimeType = 'text/plain';
      }

      const blob = new Blob([content], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      this.showAlert(`${data.emails.length} e-posta indirildi!`, 'success');
    } catch (error) {
      this.showAlert('İndirme hatası.', 'error');
    }
  }

  buildExportQuery(format = 'xlsx') {
    const params = new URLSearchParams();
    params.set('format', format);

    const verifiedOnly = document.getElementById('exportVerifiedOnly');
    const emailOnly = document.getElementById('exportEmailOnly');
    const shopType = document.getElementById('exportShopType');
    const region = document.getElementById('exportRegionFilter');

    if (verifiedOnly?.checked) params.set('verified_only', 'true');
    if (emailOnly?.checked) params.set('email_only', 'true');
    if (shopType?.value) params.set('shop_type', shopType.value);
    if (region?.value?.trim()) params.set('region', region.value.trim());

    return params.toString();
  }

  async exportResults(format = 'xlsx') {
    try {
      const query = this.buildExportQuery(format);
      const url = `/export_results?${query}`;

      if (format === 'json') {
        const { data } = await this.apiGet(url);

        if (!data.rows || data.rows.length === 0) {
          this.showAlert('Export için veri bulunamadı.', 'warning');
          return;
        }

        const blob = new Blob([JSON.stringify(data.rows, null, 2)], { type: 'application/json' });
        const link = document.createElement('a');
        const objectUrl = URL.createObjectURL(blob);
        link.href = objectUrl;
        link.download = `results_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(objectUrl);

        this.showAlert('JSON export hazırlandı!', 'success');
        return;
      }

      const link = document.createElement('a');
      link.href = url;
      link.target = '_blank';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      this.showAlert(`${format.toUpperCase()} export başlatıldı!`, 'success');
    } catch (error) {
      this.showAlert('Export hatası.', 'error');
    }
  }

  /* =========================
     REGION / QUEUE / CHARTS
  ========================= */

  async loadRegionAnalysis() {
    const tbody = document.getElementById('regionAnalysisTableBody');
    const topContainer = document.getElementById('topRegionsList');

    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">Yükleniyor...</td></tr>';
    }

    if (topContainer) {
      topContainer.innerHTML = '<div class="text-muted text-center">Yükleniyor...</div>';
    }

    try {
      const { data } = await this.apiGet('/get_region_analysis');

      if (tbody) {
        if (!data.rows || data.rows.length === 0) {
          tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">Veri bulunamadı</td></tr>';
        } else {
          tbody.innerHTML = data.rows.map(row => `
            <tr>
              <td>${row.region}</td>
              <td>${row.users_found}</td>
              <td>${row.emails_found}</td>
              <td>%${row.email_ratio}</td>
            </tr>
          `).join('');
        }
      }

      if (topContainer) {
        if (!data.top_regions || data.top_regions.length === 0) {
          topContainer.innerHTML = '<div class="text-muted text-center">Veri bulunamadı</div>';
        } else {
          topContainer.innerHTML = data.top_regions.map((row, index) => `
            <div class="d-flex justify-content-between align-items-center border-bottom py-2">
              <div>
                <strong>#${index + 1} ${row.region}</strong>
                <div class="small text-muted">${row.emails_found} mail / ${row.users_found} kullanıcı</div>
              </div>
              <span class="badge bg-success">%${row.email_ratio}</span>
            </div>
          `).join('');
        }
      }
    } catch (error) {
      if (tbody) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-danger">Bölge analizi yüklenemedi</td></tr>';
      }
      if (topContainer) {
        topContainer.innerHTML = '<div class="text-danger text-center">Bölge analizi yüklenemedi</div>';
      }
    }
  }

  async loadQueueStatus() {
    const queueSizeEl = document.getElementById('queueSize');
    const queueCurrentUserEl = document.getElementById('queueCurrentProcessingUserId');
    const dashboardCurrentUserEl = document.getElementById('dashboardCurrentProcessingUserId');
    const skippedEl = document.getElementById('skippedCount');
    const rateLimitQueueEl = document.getElementById('queueRateLimitWaits');
    const rateLimitDashboardEl = document.getElementById('dashboardRateLimitWaits');
    const nextUsersEl = document.getElementById('nextUsersList');

    try {
      const { data } = await this.apiGet('/get_queue_status');

      if (queueSizeEl) queueSizeEl.textContent = data.queue_size ?? 0;
      if (queueCurrentUserEl) queueCurrentUserEl.textContent = data.current_processing_user_id || '-';
      if (dashboardCurrentUserEl) dashboardCurrentUserEl.textContent = data.current_processing_user_id || '-';
      if (skippedEl) skippedEl.textContent = data.skipped_count ?? 0;
      if (rateLimitQueueEl) rateLimitQueueEl.textContent = data.rate_limit_waits ?? 0;
      if (rateLimitDashboardEl) rateLimitDashboardEl.textContent = data.rate_limit_waits ?? 0;

      if (nextUsersEl) {
        if (!data.next_users || data.next_users.length === 0) {
          nextUsersEl.innerHTML = '<div class="text-muted text-center">Kuyruk boş</div>';
        } else {
          nextUsersEl.innerHTML = data.next_users.map((item, index) => `
            <div class="d-flex justify-content-between align-items-center border-bottom py-2">
              <span>#${index + 1}</span>
              <span class="small">${item.user_id || '-'}</span>
            </div>
          `).join('');
        }
      }
    } catch (error) {
      if (nextUsersEl) {
        nextUsersEl.innerHTML = '<div class="text-danger text-center">Kuyruk bilgisi yüklenemedi</div>';
      }
    }
  }

  async loadChartData() {
    try {
      const { data } = await this.apiGet('/get_chart_data');

      this.renderSimpleStatList('regionChartList', data.region_distribution, 'label', 'value');
      this.renderSimpleStatList('verifiedChartList', data.verified_distribution, 'label', 'value');
      this.renderSimpleStatList('shopChartList', data.shop_distribution, 'label', 'value');
      this.renderSimpleStatList('emailChartList', data.email_distribution, 'label', 'value');
      this.renderTimelineList('emailTimelineList', data.email_timeline);
    } catch (error) {
      this.renderLoadError('regionChartList');
      this.renderLoadError('verifiedChartList');
      this.renderLoadError('shopChartList');
      this.renderLoadError('emailChartList');
      this.renderLoadError('emailTimelineList');
    }
  }

  renderSimpleStatList(containerId, rows, labelKey = 'label', valueKey = 'value') {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!rows || rows.length === 0) {
      container.innerHTML = '<div class="text-muted text-center">Veri bulunamadı</div>';
      return;
    }

    container.innerHTML = rows.map(row => `
      <div class="d-flex justify-content-between align-items-center border-bottom py-2">
        <span>${row[labelKey]}</span>
        <strong>${row[valueKey]}</strong>
      </div>
    `).join('');
  }

  renderTimelineList(containerId, rows) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!rows || rows.length === 0) {
      container.innerHTML = '<div class="text-muted text-center">Zaman verisi bulunamadı</div>';
      return;
    }

    container.innerHTML = rows.map(row => `
      <div class="d-flex justify-content-between align-items-center border-bottom py-2">
        <span>${row.time}</span>
        <strong>${row.count}</strong>
      </div>
    `).join('');
  }

  renderLoadError(containerId) {
    const container = document.getElementById(containerId);
    if (container) {
      container.innerHTML = '<div class="text-danger text-center">Veri yüklenemedi</div>';
    }
  }

  /* =========================
     RESULTS TABLE
  ========================= */

  buildResultsQuery(customPage = null, customPerPage = null) {
    const params = new URLSearchParams();
    params.set('page', String(customPage ?? this.resultsPage));
    params.set('per_page', String(customPerPage ?? this.resultsPerPage));

    const search = document.getElementById('resultsSearch')?.value?.trim();
    const region = this.getResultsRegionField()?.value?.trim();
    const verifiedOnly = document.getElementById('resultsVerifiedOnly')?.checked;
    const emailOnly = document.getElementById('resultsEmailOnly')?.checked;
    const shopType = document.getElementById('resultsShopType')?.value || 'all';

    if (search) params.set('search', search);
    if (region) params.set('region', region);
    if (verifiedOnly) params.set('verified_only', 'true');
    if (emailOnly) params.set('email_only', 'true');
    if (shopType && shopType !== 'all') params.set('shop_type', shopType);

    return params.toString();
  }

  renderEmailCell(row) {
    const email = row.email || '';
    if (email) {
      return `
        <div class="d-flex align-items-center gap-1">
          <span class="email-status-dot has-email"></span>
          <span>${email}</span>
        </div>
      `;
    }

    return `
      <div class="d-flex align-items-center gap-1">
        <span class="email-status-dot no-email"></span>
        <span class="text-muted">Yok</span>
      </div>
    `;
  }

  renderRegionBadge(region) {
    if (!region) return '<span class="text-muted">-</span>';
    return `<span class="region-badge">${region}</span>`;
  }

  renderVerifiedBadge(verified) {
    return verified
      ? `<span class="result-pill success"><i class="fas fa-check-circle"></i> Verified</span>`
      : `<span class="result-pill muted"><i class="fas fa-minus-circle"></i> No</span>`;
  }

  renderShopBadge(isShop) {
    return isShop
      ? `<span class="result-pill warning"><i class="fas fa-store"></i> Shop</span>`
      : `<span class="result-pill muted"><i class="fas fa-user"></i> Normal</span>`;
  }

  renderUsernameCell(username) {
    if (!username) return '<span class="text-muted">-</span>';
    return `<strong>@${username}</strong>`;
  }

  async loadResults() {
    if (this.resultsLoading) return;
    this.resultsLoading = true;

    const tbody = document.getElementById('resultsTableBody');
    const paginationInfo = document.getElementById('resultsPaginationInfo');

    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="10" class="text-center text-muted">Yükleniyor...</td></tr>';
    }

    try {
      const query = this.buildResultsQuery();
      const { data } = await this.apiGet(`/get_results?${query}`);

      this.resultsTotalPages = data.pages || 1;

      if (paginationInfo) {
        paginationInfo.textContent = `Sayfa ${data.page || 1} / ${data.pages || 1} • Toplam ${data.total || 0}`;
      }

      if (!tbody) return;

      if (!data.rows || data.rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="text-center text-muted">Sonuç bulunamadı</td></tr>';
        return;
      }

      tbody.innerHTML = data.rows.map((row, index) => `
        <tr>
          <td>${((data.page - 1) * data.per_page) + index + 1}</td>
          <td>${this.renderUsernameCell(row.username)}</td>
          <td>${this.renderEmailCell(row)}</td>
          <td>${row.followers || '-'}</td>
          <td>${this.renderRegionBadge(row.region)}</td>
          <td>${this.renderVerifiedBadge(row.verified)}</td>
          <td>${this.renderShopBadge(row.is_shop)}</td>
          <td class="small">${row.user_id || '-'}</td>
          <td class="small">${row.sec_uid || '-'}</td>
          <td>
            <button class="btn btn-sm btn-outline-primary" onclick="dashboard.copyResultData('${this.escapeJs(row.email || row.user_id || row.username || '')}')">
              Kopyala
            </button>
          </td>
        </tr>
      `).join('');
    } catch (error) {
      if (tbody) {
        tbody.innerHTML = '<tr><td colspan="10" class="text-center text-danger">Sonuçlar yüklenemedi</td></tr>';
      }
    } finally {
      this.resultsLoading = false;
    }
  }

  async fetchAllFilteredResults() {
    let page = 1;
    let totalPages = 1;
    const perPage = 1000;
    const allRows = [];

    do {
      const query = this.buildResultsQuery(page, perPage);
      const { response, data } = await this.apiGet(`/get_results?${query}`);

      if (!response.ok) {
        throw new Error('Filtreli sonuçlar alınamadı.');
      }

      const rows = Array.isArray(data.rows) ? data.rows : [];
      allRows.push(...rows);

      totalPages = data.pages || 1;
      page += 1;
    } while (page <= totalPages);

    return allRows;
  }

  async downloadFilteredResultsTxt() {
    try {
      this.showLoading(true);

      const rows = await this.fetchAllFilteredResults();

      if (!rows || rows.length === 0) {
        this.showAlert('Filtreye uygun sonuç bulunamadı.', 'warning');
        return;
      }

      const lines = rows
        .filter(row => row && row.username && row.email)
        .map(row => `${row.username}:${row.email}`);

      if (lines.length === 0) {
        this.showAlert('Filtreli sonuçlarda indirilecek mail bulunamadı.', 'warning');
        return;
      }

      const content = lines.join('\n');
      const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
      const objectUrl = URL.createObjectURL(blob);

      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = `filtered_results_${new Date().toISOString().split('T')[0]}.txt`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(objectUrl);

      this.showAlert(`${lines.length} filtreli kayıt indirildi!`, 'success');
    } catch (error) {
      console.error('Filtered results download error:', error);
      this.showAlert('Filtreli sonuçlar indirilemedi.', 'error');
    } finally {
      this.showLoading(false);
    }
  }

  async changeResultsPage(direction) {
    const newPage = this.resultsPage + direction;
    if (newPage < 1) return;
    if (newPage > this.resultsTotalPages) return;

    this.resultsPage = newPage;
    await this.loadResults();
  }

  async copyResultData(text) {
    try {
      await navigator.clipboard.writeText(text);
      this.showAlert('Kopyalandı!', 'success');
    } catch (error) {
      this.showAlert('Kopyalama başarısız.', 'error');
    }
  }

  escapeJs(value) {
    return String(value)
      .replace(/\\/g, '\\\\')
      .replace(/'/g, "\\'")
      .replace(/"/g, '\\"')
      .replace(/\n/g, ' ')
      .replace(/\r/g, ' ');
  }

  /* =========================
     USERS / ADMIN
  ========================= */

  async loadUsers() {
    try {
      const { data } = await this.apiGet('/get_users');
      if (data.users) this.renderUsers(data.users);
    } catch (error) {
      console.error('Users load error:', error);
    }
  }

  renderUsers(users) {
    const tbody = document.getElementById('usersTableBody');
    if (!tbody) return;

    if (!users || users.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" class="text-center">Kullanıcı bulunamadı</td></tr>';
      return;
    }

    const usersHtml = users.map(user => {
      const packageType = user.package_type || '-';
      const isFrozen = !!user.is_frozen;
      const dailyLimit = user.daily_scrape_limit ?? '-';
      const lastDevice = user.last_login_device || '-';

      return `
        <tr>
          <td>
            <strong>${user.username}</strong>
            ${user.username === 'talha' ? '<span class="badge bg-warning ms-1">Ana Admin</span>' : ''}
          </td>
          <td><span class="badge ${user.role === 'admin' ? 'bg-danger' : 'bg-primary'}">${user.role}</span></td>
          <td>${packageType}</td>
          <td>${isFrozen ? '<span class="badge bg-warning">Donuk</span>' : '<span class="badge bg-success">Aktif</span>'}</td>
          <td>${dailyLimit}</td>
          <td><small>${user.last_login || 'Hiç giriş yapmamış'}</small></td>
          <td><small>${lastDevice}</small></td>
          <td>
            <button class="btn btn-sm btn-outline-info" onclick="dashboard.showUserEmails('${user.username}')">
              <i class="fas fa-envelope"></i>
            </button>
          </td>
          <td>
            ${user.username !== 'talha' ? `
              <button class="btn btn-sm btn-outline-danger" onclick="dashboard.deleteUser('${user.username}')">
                <i class="fas fa-trash"></i>
              </button>
            ` : '<span class="text-muted">-</span>'}
          </td>
        </tr>
      `;
    }).join('');

    tbody.innerHTML = usersHtml;
  }

  async addUser() {
    const username = document.getElementById('newUsername')?.value.trim() || '';
    const password = document.getElementById('newPassword')?.value.trim() || '';
    const role = document.getElementById('newUserRole')?.value || 'user';

    if (!username || !password) {
      this.showAlert('Kullanıcı adı ve şifre gerekli.', 'warning');
      return;
    }

    try {
      const { data } = await this.apiPost('/add_user', { username, password, role });

      if (data.success) {
        this.showAlert('Kullanıcı başarıyla eklendi!', 'success');
        if (document.getElementById('newUsername')) document.getElementById('newUsername').value = '';
        if (document.getElementById('newPassword')) document.getElementById('newPassword').value = '';
        if (document.getElementById('newUserRole')) document.getElementById('newUserRole').value = 'user';
        this.loadUsers();
        this.loadAdminOverview();
        this.loadPackageSummary();
      } else {
        this.showAlert(data.error || 'Kullanıcı eklenemedi.', 'error');
      }
    } catch (error) {
      this.showAlert('Bağlantı hatası.', 'error');
    }
  }

  async deleteUser(username) {
    if (!confirm(`${username} kullanıcısını silmek istediğinizden emin misiniz?`)) return;

    try {
      const { data } = await this.apiPost('/delete_user', { username });

      if (data.success) {
        this.showAlert('Kullanıcı başarıyla silindi!', 'success');
        this.loadUsers();
        this.loadAdminOverview();
        this.loadPackageSummary();
      } else {
        this.showAlert(data.error || 'Kullanıcı silinemedi.', 'error');
      }
    } catch (error) {
      this.showAlert('Bağlantı hatası.', 'error');
    }
  }

  async showUserEmails(username) {
    try {
      const { data } = await this.apiGet(`/get_user_emails?username=${encodeURIComponent(username)}`);

      let modalHtml = `
        <div class="modal fade user-emails-modal" tabindex="-1">
          <div class="modal-dialog modal-lg">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title">${username} - Toplanan E-postalar</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
              </div>
              <div class="modal-body">
                <div class="user-emails-list">
      `;

      if (data.emails && data.emails.length > 0) {
        modalHtml += data.emails.map(email => `
          <div class="user-email-item">
            <div class="email-info">
              <div>
                <div class="email-address">${email.email}</div>
                <div class="email-meta">
                  @${email.username} • ${email.followers} takipçi${email.region ? ` • ${email.region}` : ''} • ${email.timestamp}
                </div>
              </div>
              <div>
                ${email.verified ? '<span class="badge bg-success">✓</span>' : ''}
                ${email.ttseller ? '<span class="badge bg-warning">🛍️</span>' : ''}
              </div>
            </div>
          </div>
        `).join('');
      } else {
        modalHtml += `<div class="text-muted text-center">${data.message || 'E-posta bulunamadı'}</div>`;
      }

      modalHtml += `
                </div>
              </div>
              <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Kapat</button>
              </div>
            </div>
          </div>
        </div>
      `;

      const existingModal = document.querySelector('.user-emails-modal');
      if (existingModal) existingModal.remove();

      document.body.insertAdjacentHTML('beforeend', modalHtml);
      const modalEl = document.querySelector('.user-emails-modal');
      const modal = new bootstrap.Modal(modalEl);
      modal.show();

      modalEl.addEventListener('hidden.bs.modal', function () {
        this.remove();
      });
    } catch (error) {
      this.showAlert('E-postalar yüklenemedi.', 'error');
    }
  }

  async loadBlockedIps() {
    try {
      const { data } = await this.apiGet('/get_blocked_ips');
      if (data.blocked_ips) this.renderBlockedIps(data.blocked_ips);
    } catch (error) {
      console.error('Blocked IPs load error:', error);
    }
  }

  renderBlockedIps(blockedIps) {
    const container = document.getElementById('blockedIpsList');
    if (!container) return;

    if (!blockedIps || blockedIps.length === 0) {
      container.innerHTML = '<div class="text-muted text-center">Engellenen IP bulunamadı...</div>';
      return;
    }

    container.innerHTML = blockedIps.map(ip => `
      <div class="blocked-ip-item">
        <span class="ip-address">${ip}</span>
        <button class="btn btn-sm btn-outline-success" onclick="dashboard.unblockIp('${ip}')">
          <i class="fas fa-unlock"></i> Engeli Kaldır
        </button>
      </div>
    `).join('');
  }

  async blockIp() {
    const ip = document.getElementById('blockIpInput')?.value.trim() || '';

    if (!ip) {
      this.showAlert('IP adresi gerekli.', 'warning');
      return;
    }

    try {
      const { data } = await this.apiPost('/block_ip', { ip });

      if (data.success) {
        this.showAlert(`IP ${ip} engellendi!`, 'success');
        if (document.getElementById('blockIpInput')) document.getElementById('blockIpInput').value = '';
        this.loadBlockedIps();
        this.loadAdminOverview();
      } else {
        this.showAlert(data.error || 'IP engellenemedi.', 'error');
      }
    } catch (error) {
      this.showAlert('Bağlantı hatası.', 'error');
    }
  }

  async unblockIp(ip) {
    if (!confirm(`${ip} IP adresinin engelini kaldırmak istediğinizden emin misiniz?`)) return;

    try {
      const { data } = await this.apiPost('/unblock_ip', { ip });

      if (data.success) {
        this.showAlert(`IP ${ip} engeli kaldırıldı!`, 'success');
        this.loadBlockedIps();
        this.loadAdminOverview();
      } else {
        this.showAlert(data.error || 'IP engeli kaldırılamadı.', 'error');
      }
    } catch (error) {
      this.showAlert('Bağlantı hatası.', 'error');
    }
  }

  async loadAdminOverview() {
    if (window.userRole !== 'admin') return;

    try {
      const { data: systemStats } = await this.apiGet('/get_system_stats');

      this.setText('adminTotalUsers', systemStats.total_users ?? 0);
      this.setText('adminActiveUsers', systemStats.active_users ?? 0);
      this.setText('adminTotalEmailsFound', systemStats.total_emails_found ?? 0);
      this.setText('adminTotalResults', systemStats.total_results ?? 0);
      this.setText('adminTotalProcessedGlobal', systemStats.total_processed_global ?? 0);
      this.setText('adminBlockedIpsCount', systemStats.blocked_ips ?? 0);

      this.setText('adminOverviewTotalUsers', systemStats.total_users ?? 0);
      this.setText('adminOverviewActiveUsers', systemStats.active_users ?? 0);
      this.setText('adminOverviewEmails', systemStats.total_emails_found ?? 0);
      this.setText('adminOverviewResults', systemStats.total_results ?? 0);
      this.setText('adminOverviewBlockedIps', systemStats.blocked_ips ?? 0);
      this.setText('adminOverviewExports', systemStats.total_exports ?? 0);

      const tbody = document.getElementById('adminOverviewTableBody');
      if (!tbody) return;

      try {
        const { data: usersData } = await this.apiGet('/get_users');
        const users = Array.isArray(usersData.users) ? usersData.users : [];

        if (users.length === 0) {
          tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">Veri bulunamadı</td></tr>';
          return;
        }

        tbody.innerHTML = users.map(user => `
          <tr>
            <td>${user.username}</td>
            <td>${user.package_type || '-'}</td>
            <td>${user.is_frozen ? '<span class="badge bg-warning">Donuk</span>' : '<span class="badge bg-success">Aktif</span>'}</td>
            <td>${user.daily_scrape_limit ?? '-'}</td>
            <td>${user.current_emails_found ?? user.total_mail_found ?? 0}</td>
            <td>${user.total_active_time || '-'}</td>
            <td>${user.total_export_count ?? 0}</td>
            <td>${user.last_login_device || '-'}</td>
          </tr>
        `).join('');
      } catch (_) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">Kullanıcı performans verisi alınamadı</td></tr>';
      }
    } catch (error) {
      const tbody = document.getElementById('adminOverviewTableBody');
      if (tbody) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center text-danger">Admin özet verisi yüklenemedi</td></tr>';
      }
    }
  }

  async loadPackageSummary() {
    if (window.userRole !== 'admin') return;

    const tbody = document.getElementById('packageTableBody');
    if (!tbody) return;

    try {
      const { data } = await this.apiGet('/get_users');
      const users = Array.isArray(data.users) ? data.users : [];

      if (users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Veri bulunamadı</td></tr>';
        this.setText('trialUsersCount', 0);
        this.setText('premiumUsersCount', 0);
        this.setText('enterpriseUsersCount', 0);
        return;
      }

      let trial = 0;
      let premium = 0;
      let enterprise = 0;

      tbody.innerHTML = users.map(user => {
        const pkg = String(user.package_type || 'trial').toLowerCase();
        if (pkg === 'trial') trial += 1;
        else if (pkg === 'premium') premium += 1;
        else if (pkg === 'enterprise') enterprise += 1;

        return `
          <tr>
            <td>${user.username}</td>
            <td>${user.package_type || 'trial'}</td>
            <td>${user.daily_scrape_limit ?? '-'}</td>
            <td>${user.total_scrape_limit ?? '-'}</td>
            <td>${user.daily_scrape_used ?? 0}</td>
            <td>${user.is_frozen ? '<span class="badge bg-warning">Donuk</span>' : '<span class="badge bg-success">Aktif</span>'}</td>
          </tr>
        `;
      }).join('');

      this.setText('trialUsersCount', trial);
      this.setText('premiumUsersCount', premium);
      this.setText('enterpriseUsersCount', enterprise);
    } catch (error) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Paket verisi yüklenemedi</td></tr>';
    }
  }

  async findUserByUsername(username) {
    const { data } = await this.apiGet('/get_users');
    const users = Array.isArray(data.users) ? data.users : [];
    return users.find(u => u.username === username) || null;
  }

  async freezeUser() {
    const username = document.getElementById('adminActionUsername')?.value.trim() || '';
    if (!username) {
      this.showAlert('Önce kullanıcı adı gir.', 'warning');
      return;
    }

    try {
      const user = await this.findUserByUsername(username);
      if (!user) {
        this.showAlert('Kullanıcı bulunamadı.', 'error');
        return;
      }

      if (user.is_frozen) {
        this.showAlert('Kullanıcı zaten donuk durumda.', 'info');
        return;
      }

      const { response, data } = await this.apiPost('/toggle_user_freeze', { username });

      if (response.ok && data.success) {
        this.showAlert('Kullanıcı donduruldu!', 'success');
        this.loadUsers();
        this.loadAdminOverview();
        this.loadPackageSummary();
      } else {
        this.showAlert(data.error || 'Kullanıcı dondurulamadı.', 'error');
      }
    } catch (error) {
      this.showAlert('Freeze işleminde hata oluştu.', 'error');
    }
  }

  async unfreezeUser() {
    const username = document.getElementById('adminActionUsername')?.value.trim() || '';
    if (!username) {
      this.showAlert('Önce kullanıcı adı gir.', 'warning');
      return;
    }

    try {
      const user = await this.findUserByUsername(username);
      if (!user) {
        this.showAlert('Kullanıcı bulunamadı.', 'error');
        return;
      }

      if (!user.is_frozen) {
        this.showAlert('Kullanıcı zaten aktif.', 'info');
        return;
      }

      const { response, data } = await this.apiPost('/toggle_user_freeze', { username });

      if (response.ok && data.success) {
        this.showAlert('Kullanıcı tekrar aktif edildi!', 'success');
        this.loadUsers();
        this.loadAdminOverview();
        this.loadPackageSummary();
      } else {
        this.showAlert(data.error || 'Kullanıcı aktif edilemedi.', 'error');
      }
    } catch (error) {
      this.showAlert('Unfreeze işleminde hata oluştu.', 'error');
    }
  }

  async resetUserLimits() {
    const username = document.getElementById('adminActionUsername')?.value.trim() || '';
    if (!username) {
      this.showAlert('Önce kullanıcı adı gir.', 'warning');
      return;
    }

    this.showAlert('Backend tarafında reset_user_limits endpointi yok.', 'warning');
  }

  async savePackageSettings() {
    const username = document.getElementById('packageUsername')?.value.trim() || '';
    const packageType = document.getElementById('packageType')?.value || 'trial';
    const accountType = document.getElementById('accountType')?.value || packageType;
    const dailyScrapeLimit = parseInt(document.getElementById('dailyScrapeLimit')?.value, 10) || 0;
    const totalScrapeLimit = parseInt(document.getElementById('totalScrapeLimit')?.value, 10) || 0;
    const isFrozen = !!document.getElementById('packageIsFrozen')?.checked;

    if (!username) {
      this.showAlert('Kullanıcı adı gerekli.', 'warning');
      return;
    }

    try {
      const { response, data } = await this.apiPost('/update_user_plan', {
        username,
        packageType,
        accountType,
        dailyScrapeLimit,
        totalScrapeLimit,
        isFrozen
      });

      if (response.ok && data.success) {
        this.showAlert('Paket / limit kaydedildi!', 'success');
        this.loadUsers();
        this.loadAdminOverview();
        this.loadPackageSummary();
      } else {
        this.showAlert(data.error || 'Paket güncellenemedi.', 'error');
      }
    } catch (error) {
      this.showAlert('Paket kaydında hata oluştu.', 'error');
    }
  }

  /* =========================
     APPEARANCE
  ========================= */

  loadAppearanceSettings() {
    const themeToggle = document.getElementById('themeToggle');
    const accentColorSelect = document.getElementById('accentColorSelect');

    const savedTheme = localStorage.getItem('dashboard_theme') || 'dark';
    const savedAccent = localStorage.getItem('dashboard_accent') || 'pink';

    document.body.setAttribute('data-theme', savedTheme);
    document.body.setAttribute('data-accent', savedAccent);

    if (themeToggle) {
      themeToggle.checked = savedTheme === 'light';
    }

    if (accentColorSelect) {
      accentColorSelect.value = savedAccent;
    }
  }

  previewAppearanceSettings() {
    const themeToggle = document.getElementById('themeToggle');
    const accentColorSelect = document.getElementById('accentColorSelect');

    const theme = themeToggle?.checked ? 'light' : 'dark';
    const accent = accentColorSelect?.value || 'pink';

    document.body.setAttribute('data-theme', theme);
    document.body.setAttribute('data-accent', accent);
  }

  saveAppearanceSettings() {
    const themeToggle = document.getElementById('themeToggle');
    const accentColorSelect = document.getElementById('accentColorSelect');

    const theme = themeToggle?.checked ? 'light' : 'dark';
    const accent = accentColorSelect?.value || 'pink';

    localStorage.setItem('dashboard_theme', theme);
    localStorage.setItem('dashboard_accent', accent);

    document.body.setAttribute('data-theme', theme);
    document.body.setAttribute('data-accent', accent);

    this.showAlert('Görünüm ayarları kaydedildi!', 'success');
  }

  /* =========================
     UPDATERS
  ========================= */

  startStatsUpdater() {
    this.updateStats();
    this.statsUpdateInterval = setInterval(() => {
      this.updateStats();
      this.loadQueueStatus();

      if (window.userRole === 'admin' && this.currentSection === 'admin-overview') {
        this.loadAdminOverview();
      }
    }, 1000);
  }

  startLogUpdater() {
    this.updateLogs();
    this.logUpdateInterval = setInterval(() => {
      this.updateLogs();

      if (this.currentSection === 'charts') this.loadChartData();
      if (window.userRole === 'admin' && this.currentSection === 'admin-packages') {
        this.loadPackageSummary();
      }

      // region-analysis burada otomatik yenilenmeyecek
      // results burada otomatik yenilenmeyecek
    }, 1000);
  }

  async updateStats() {
    try {
      const { data: stats } = await this.apiGet('/get_stats');

      this.setText('totalEmails', stats.emails ?? 0);
      this.setText('shopEmails', stats.shop_emails ?? 0);
      this.setText('normalEmails', stats.normal_emails ?? 0);
      this.setText('inProcess', stats.inprocess ?? 0);
      this.setText('checkedUsers', stats.checked ?? 0);
      this.setText('elapsedTime', stats.elapsed_time || '00:00:00');
      this.setText('lastUpdate', new Date().toLocaleTimeString());

      const startTimeEl = document.getElementById('startTime');
      if (startTimeEl) {
        if (stats.is_scraping && !startTimeEl.textContent.includes(':')) {
          startTimeEl.textContent = new Date().toLocaleTimeString();
        } else if (!stats.is_scraping) {
          startTimeEl.textContent = '-';
        }
      }

      this.setText('resultsCount', stats.results_count ?? 0);
      this.setText('skippedUsersStat', stats.skipped_count ?? 0);
      this.setText('rateLimitWaitsStat', stats.rate_limit_waits ?? 0);
      this.setText('currentUserStat', stats.current_processing_user_id || '-');
      this.setText('dashboardCurrentProcessingUserId', stats.current_processing_user_id || '-');
      this.setText('dashboardRateLimitWaits', stats.rate_limit_waits ?? 0);

      if (stats.filters && !this.filtersInitialized) {
        this.applyFiltersToUI(stats.filters);
        this.filtersInitialized = true;
      }

      this.renderRecentUsers(stats.recent_users || []);
      this.isScrapingActive = !!stats.is_scraping;
      this.updateScraperButtons();
    } catch (error) {
      console.error('Stats update error:', error);
    }
  }

  setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  renderRecentUsers(recentUsers) {
    const container = document.getElementById('recentUsers');
    if (!container) return;

    if (!recentUsers || recentUsers.length === 0) {
      container.innerHTML = '<div class="text-muted text-center">Henüz kullanıcı eklenmedi...</div>';
      return;
    }

    container.innerHTML = recentUsers.map(user => `
      <div class="recent-user-item">
        <div class="recent-user-info">
          <h6>@${user.username}</h6>
          <small>
            ${user.email || 'E-posta yok'} • ${user.followers} takipçi${user.region ? ` • ${user.region}` : ''} • ${user.timestamp}
          </small>
        </div>
        <div class="recent-user-badges">
          ${user.verified ? '<span class="badge bg-success">✓</span>' : ''}
          ${user.ttseller ? '<span class="badge bg-warning">🛍️</span>' : ''}
        </div>
      </div>
    `).join('');
  }

  async updateLogs() {
    try {
      const [{ data: logsData }, { data: mailLogsData }] = await Promise.all([
        this.apiGet('/get_logs'),
        this.apiGet('/get_mail_logs')
      ]);

      this.renderLogs('logsContainer', logsData.logs);
      this.renderLogs('mailLogsContainer', mailLogsData.logs);
    } catch (error) {
      console.error('Logs update error:', error);
    }
  }

  renderLogs(containerId, logs) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!logs || logs.length === 0) {
      container.innerHTML = '<div class="text-muted text-center">Log mesajları burada görünecek...</div>';
      return;
    }

    const atBottom =
      Math.abs(container.scrollHeight - container.clientHeight - container.scrollTop) < 20;

    const logsHtml = logs.map(log => {
      const logType = typeof log === 'object' ? log.type : 'info';
      const logMessage = typeof log === 'object' ? log.message : log;
      const logTime = typeof log === 'object' ? log.timestamp : new Date().toLocaleTimeString();

      return `
        <div class="log-entry ${logType}">
          <span class="log-timestamp">${logTime}</span>
          ${logMessage}
        </div>
      `;
    }).join('');

    container.innerHTML = logsHtml;

    if (atBottom) {
      container.scrollTop = container.scrollHeight;
    }
  }

  /* =========================
     HELPERS
  ========================= */

  showAlert(message, type) {
    const typeMap = {
      error: 'danger',
      warning: 'warning',
      success: 'success',
      info: 'info'
    };

    const bsType = typeMap[type] || type || 'info';

    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${bsType} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    alertDiv.innerHTML = `
      ${message}
      <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.body.appendChild(alertDiv);

    setTimeout(() => {
      if (alertDiv.parentNode) alertDiv.remove();
    }, 5000);
  }

  showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (!overlay) return;

    if (show) overlay.classList.remove('d-none');
    else overlay.classList.add('d-none');
  }
}

document.addEventListener('DOMContentLoaded', function () {
  window.dashboard = new Dashboard();
});