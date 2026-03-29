document.addEventListener('DOMContentLoaded', function () {
  const loginForm = document.getElementById('loginForm');
  const usernameInput = document.getElementById('username');
  const passwordInput = document.getElementById('password');

  const loginBtn = document.querySelector('.login-btn');
  const btnText = document.querySelector('.btn-text');
  const btnLoading = document.querySelector('.btn-loading');

  const errorAlert = document.getElementById('errorAlert');
  const errorMessage = document.getElementById('errorMessage');

  const togglePasswordBtn = document.getElementById('togglePasswordBtn');
  const togglePasswordIcon = document.getElementById('togglePasswordIcon');

  const istanbulClock = document.getElementById('istanbulClock');
  const istanbulDate = document.getElementById('istanbulDate');
  const istanbulWeatherTemp = document.getElementById('istanbulWeatherTemp');
  const istanbulWeatherText = document.getElementById('istanbulWeatherText');
  const weatherIcon = document.getElementById('weatherIcon');

  let errorTimeout = null;
  let isSubmitting = false;

  init();

  function init() {
    bindEvents();
    startIstanbulClock();
    loadIstanbulWeather();
    setInterval(loadIstanbulWeather, 10 * 60 * 1000);
  }

  function bindEvents() {
    if (loginForm) {
      loginForm.addEventListener('submit', handleLoginSubmit);
    }

    if (passwordInput) {
      passwordInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          loginForm.requestSubmit();
        }
      });
    }

    if (togglePasswordBtn) {
      togglePasswordBtn.addEventListener('click', togglePasswordVisibility);
    }

    if (usernameInput) {
      usernameInput.addEventListener('input', hideError);
    }

    if (passwordInput) {
      passwordInput.addEventListener('input', hideError);
    }
  }

  async function handleLoginSubmit(e) {
    e.preventDefault();

    if (isSubmitting) return;

    const username = usernameInput ? usernameInput.value.trim() : '';
    const password = passwordInput ? passwordInput.value.trim() : '';

    if (!username || !password) {
      showError('Lütfen tüm alanları doldurun.');
      return;
    }

    hideError();
    setLoadingState(true);
    isSubmitting = true;

    try {
      const response = await fetch('/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          username,
          password
        })
      });

      let data = {};
      try {
        data = await response.json();
      } catch (_) {
        data = {};
      }

      if (response.ok && data.success) {
        setSuccessState();
        setTimeout(() => {
          window.location.href = '/dashboard';
        }, 900);
        return;
      }

      showError(data.message || 'Giriş başarısız. Lütfen tekrar deneyin.');
      setLoadingState(false);
      isSubmitting = false;
    } catch (error) {
      showError('Bağlantı hatası. Lütfen tekrar deneyin.');
      setLoadingState(false);
      isSubmitting = false;
    }
  }

  function setLoadingState(loading) {
    if (!loginBtn || !btnText || !btnLoading) return;

    if (loading) {
      btnText.classList.add('d-none');
      btnLoading.classList.remove('d-none');
      loginBtn.disabled = true;
    } else {
      btnText.classList.remove('d-none');
      btnLoading.classList.add('d-none');
      loginBtn.disabled = false;
      loginBtn.classList.remove('btn-success');
      if (!loginBtn.classList.contains('btn-primary')) {
        loginBtn.classList.add('btn-primary');
      }
    }
  }

  function setSuccessState() {
    if (!loginBtn || !btnText || !btnLoading) return;

    btnText.classList.add('d-none');
    btnLoading.classList.add('d-none');
    loginBtn.disabled = true;
    loginBtn.classList.remove('btn-primary');
    loginBtn.classList.add('btn-success');
    loginBtn.innerHTML = '<i class="fas fa-check"></i> Giriş Başarılı!';
  }

  function showError(message) {
    if (!errorAlert || !errorMessage) return;

    clearTimeout(errorTimeout);
    errorMessage.textContent = message;
    errorAlert.classList.remove('d-none');

    errorTimeout = setTimeout(() => {
      hideError();
    }, 5000);
  }

  function hideError() {
    if (!errorAlert) return;
    errorAlert.classList.add('d-none');
  }

  function togglePasswordVisibility() {
    if (!passwordInput || !togglePasswordIcon) return;

    const isPassword = passwordInput.type === 'password';
    passwordInput.type = isPassword ? 'text' : 'password';

    togglePasswordIcon.classList.remove('fa-eye', 'fa-eye-slash');
    togglePasswordIcon.classList.add(isPassword ? 'fa-eye-slash' : 'fa-eye');
  }

  function startIstanbulClock() {
    updateIstanbulClock();
    setInterval(updateIstanbulClock, 1000);
  }

  function updateIstanbulClock() {
    const now = new Date();

    if (istanbulClock) {
      istanbulClock.textContent = now.toLocaleTimeString('tr-TR', {
        timeZone: 'Europe/Istanbul',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      });
    }

    if (istanbulDate) {
      istanbulDate.textContent = now.toLocaleDateString('tr-TR', {
        timeZone: 'Europe/Istanbul',
        weekday: 'long',
        day: '2-digit',
        month: 'long',
        year: 'numeric'
      });
    }
  }

  async function loadIstanbulWeather() {
    if (!istanbulWeatherTemp || !istanbulWeatherText) return;

    try {
      const url =
        'https://api.open-meteo.com/v1/forecast?latitude=41.0082&longitude=28.9784&current=temperature_2m,weather_code&timezone=Europe%2FIstanbul';

      const response = await fetch(url);
      const data = await response.json();

      const current = data && data.current ? data.current : null;
      if (!current) {
        throw new Error('Weather data unavailable');
      }

      const temp = Math.round(current.temperature_2m);
      const weatherCode = current.weather_code;

      istanbulWeatherTemp.textContent = `${temp}°C`;
      istanbulWeatherText.textContent = getWeatherDescription(weatherCode);
      updateWeatherIcon(weatherCode);
    } catch (error) {
      istanbulWeatherTemp.textContent = '--°C';
      istanbulWeatherText.textContent = 'Hava durumu alınamadı';
      if (weatherIcon) {
        weatherIcon.className = 'fas fa-cloud';
      }
    }
  }

  function getWeatherDescription(code) {
    const map = {
      0: 'Açık',
      1: 'Az bulutlu',
      2: 'Parçalı bulutlu',
      3: 'Kapalı',
      45: 'Sisli',
      48: 'Yoğun sis',
      51: 'Hafif çisenti',
      53: 'Çisenti',
      55: 'Yoğun çisenti',
      56: 'Hafif donan çisenti',
      57: 'Yoğun donan çisenti',
      61: 'Hafif yağmur',
      63: 'Yağmurlu',
      65: 'Kuvvetli yağmur',
      66: 'Hafif donan yağmur',
      67: 'Kuvvetli donan yağmur',
      71: 'Hafif kar',
      73: 'Kar yağışı',
      75: 'Yoğun kar',
      77: 'Kar taneli',
      80: 'Hafif sağanak',
      81: 'Sağanak',
      82: 'Kuvvetli sağanak',
      85: 'Hafif kar sağanağı',
      86: 'Yoğun kar sağanağı',
      95: 'Fırtınalı',
      96: 'Dolu ihtimalli fırtına',
      99: 'Kuvvetli dolulu fırtına'
    };

    return map[code] || 'Bilinmeyen hava';
  }

  function updateWeatherIcon(code) {
    if (!weatherIcon) return;

    let iconClass = 'fas fa-cloud-sun';

    if (code === 0) {
      iconClass = 'fas fa-sun';
    } else if ([1, 2].includes(code)) {
      iconClass = 'fas fa-cloud-sun';
    } else if (code === 3) {
      iconClass = 'fas fa-cloud';
    } else if ([45, 48].includes(code)) {
      iconClass = 'fas fa-smog';
    } else if ([51, 53, 55, 56, 57].includes(code)) {
      iconClass = 'fas fa-cloud-rain';
    } else if ([61, 63, 65, 66, 67, 80, 81, 82].includes(code)) {
      iconClass = 'fas fa-cloud-showers-heavy';
    } else if ([71, 73, 75, 77, 85, 86].includes(code)) {
      iconClass = 'fas fa-snowflake';
    } else if ([95, 96, 99].includes(code)) {
      iconClass = 'fas fa-bolt';
    }

    weatherIcon.className = iconClass;
  }
});