/**
 * CASHFLIP - 3D Casino Game Engine
 * Three.js scene + API integration + full game flow
 */

(function() {
    'use strict';

    // ==================== STATE ====================
    const state = {
        token: localStorage.getItem('cf_access_token') || null,
        refreshToken: localStorage.getItem('cf_refresh_token') || null,
        player: null,
        session: null,
        isFlipping: false,
        otpChannel: 'sms',
        otpPhone: '',
        refCode: new URLSearchParams(window.location.search).get('ref') || '',
    };

    // ==================== API ====================
    const API = {
        base: '/api',

        _refreshing: null,

        async request(url, options = {}) {
            const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
            if (state.token) headers['Authorization'] = `Bearer ${state.token}`;

            const resp = await fetch(this.base + url, { ...options, headers });

            if ((resp.status === 401 || resp.status === 403) && state.refreshToken) {
                const refreshed = await this.refreshToken();
                if (refreshed) {
                    headers['Authorization'] = `Bearer ${state.token}`;
                    return fetch(this.base + url, { ...options, headers });
                }
            }
            return resp;
        },

        async get(url) { return this.request(url); },

        async post(url, data) {
            return this.request(url, { method: 'POST', body: JSON.stringify(data) });
        },

        async patch(url, data) {
            return this.request(url, { method: 'PATCH', body: JSON.stringify(data) });
        },

        async refreshToken() {
            if (this._refreshing) return this._refreshing;
            this._refreshing = (async () => {
                try {
                    const resp = await fetch(this.base + '/accounts/auth/refresh/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ refresh_token: state.refreshToken }),
                    });
                    if (resp.ok) {
                        const data = await resp.json();
                        state.token = data.access_token;
                        localStorage.setItem('cf_access_token', data.access_token);
                        scheduleTokenRefresh();
                        return true;
                    }
                } catch (e) { console.error('Refresh failed:', e); }
                logout();
                return false;
            })();
            const result = await this._refreshing;
            this._refreshing = null;
            return result;
        },
    };

    // ==================== PROACTIVE TOKEN REFRESH ====================
    let refreshTimer = null;
    function scheduleTokenRefresh() {
        if (refreshTimer) clearTimeout(refreshTimer);
        if (!state.token) return;
        try {
            const payload = JSON.parse(atob(state.token.split('.')[1]));
            const expiresAt = payload.exp * 1000;
            const refreshAt = expiresAt - 2 * 60 * 1000;
            const delay = Math.max(refreshAt - Date.now(), 10000);
            refreshTimer = setTimeout(() => {
                if (state.refreshToken) API.refreshToken();
            }, delay);
        } catch (e) { /* invalid token format, ignore */ }
    }

    // ==================== THREE.JS SCENE ====================
    let scene, camera, renderer, banknote, particles;
    let noteGeometry, noteFrontMat, noteBackMat;
    let animationId;

    function initScene() {
        const canvas = document.getElementById('game-canvas');
        if (!canvas) return;

        scene = new THREE.Scene();
        scene.background = new THREE.Color(0x0a0e17);
        scene.fog = new THREE.FogExp2(0x0a0e17, 0.015);

        camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 100);
        camera.position.set(0, 0, 5);

        renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

        // Lighting
        const ambientLight = new THREE.AmbientLight(0x404060, 0.6);
        scene.add(ambientLight);

        const spotLight = new THREE.SpotLight(0xffd700, 1.5, 20, Math.PI / 4, 0.5);
        spotLight.position.set(0, 5, 5);
        scene.add(spotLight);

        const pointLight1 = new THREE.PointLight(0x00ff88, 0.4, 15);
        pointLight1.position.set(-5, 2, 3);
        scene.add(pointLight1);

        const pointLight2 = new THREE.PointLight(0x00d4ff, 0.4, 15);
        pointLight2.position.set(5, 2, 3);
        scene.add(pointLight2);

        // Casino table (felt surface)
        const tableGeo = new THREE.PlaneGeometry(20, 12);
        const tableMat = new THREE.MeshStandardMaterial({
            color: 0x0d4d2b, roughness: 0.8, metalness: 0.1,
        });
        const table = new THREE.Mesh(tableGeo, tableMat);
        table.rotation.x = -Math.PI / 2;
        table.position.y = -2;
        scene.add(table);

        // Banknote card
        noteGeometry = new THREE.BoxGeometry(3, 1.8, 0.02);
        noteFrontMat = new THREE.MeshStandardMaterial({
            color: 0xffd700, roughness: 0.3, metalness: 0.6,
            emissive: 0x332200, emissiveIntensity: 0.2,
        });
        noteBackMat = new THREE.MeshStandardMaterial({
            color: 0x1a3a2a, roughness: 0.4, metalness: 0.3,
        });
        const sideMat = new THREE.MeshStandardMaterial({ color: 0xb8860b });

        banknote = new THREE.Mesh(noteGeometry, [
            sideMat, sideMat, sideMat, sideMat, noteFrontMat, noteBackMat,
        ]);
        banknote.position.set(0, 0, 0);
        scene.add(banknote);

        // Particles
        const particleGeo = new THREE.BufferGeometry();
        const particleCount = 200;
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);

        for (let i = 0; i < particleCount; i++) {
            positions[i * 3] = (Math.random() - 0.5) * 20;
            positions[i * 3 + 1] = (Math.random() - 0.5) * 10;
            positions[i * 3 + 2] = (Math.random() - 0.5) * 10;
            const c = new THREE.Color().setHSL(0.12 + Math.random() * 0.1, 0.8, 0.6);
            colors[i * 3] = c.r;
            colors[i * 3 + 1] = c.g;
            colors[i * 3 + 2] = c.b;
        }

        particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        particleGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

        const particleMat = new THREE.PointsMaterial({
            size: 0.05, vertexColors: true, transparent: true, opacity: 0.6,
        });
        particles = new THREE.Points(particleGeo, particleMat);
        scene.add(particles);

        // Animate
        function animate() {
            animationId = requestAnimationFrame(animate);

            // Gentle banknote hover
            if (!state.isFlipping) {
                banknote.rotation.y += 0.002;
                banknote.position.y = Math.sin(Date.now() * 0.001) * 0.1;
            }

            // Particle drift
            particles.rotation.y += 0.0003;

            renderer.render(scene, camera);
        }
        animate();

        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
    }

    function flipAnimation(isZero, value) {
        return new Promise((resolve) => {
            state.isFlipping = true;
            const startTime = Date.now();
            const duration = 1200;
            const totalRotations = 4;

            // Set color based on result
            if (isZero) {
                noteFrontMat.color.setHex(0xff0000);
                noteFrontMat.emissive.setHex(0x440000);
            } else {
                noteFrontMat.color.setHex(0xffd700);
                noteFrontMat.emissive.setHex(0x332200);
            }

            function animateFlip() {
                const elapsed = Date.now() - startTime;
                const progress = Math.min(elapsed / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic

                // Spin Y
                banknote.rotation.y = eased * Math.PI * 2 * totalRotations;

                // Rise and fall
                const peakHeight = 1.5;
                banknote.position.y = Math.sin(progress * Math.PI) * peakHeight;

                // Slight wobble
                banknote.rotation.z = Math.sin(progress * Math.PI * 6) * 0.1 * (1 - progress);

                if (progress < 1) {
                    requestAnimationFrame(animateFlip);
                } else {
                    banknote.rotation.y = 0;
                    banknote.rotation.z = 0;
                    banknote.position.y = 0;
                    state.isFlipping = false;
                    resolve();
                }
            }
            animateFlip();
        });
    }

    function winCelebration() {
        // Flash green particles
        if (particles && particles.material) {
            const origOpacity = particles.material.opacity;
            particles.material.opacity = 1;
            particles.material.size = 0.12;
            setTimeout(() => {
                particles.material.opacity = origOpacity;
                particles.material.size = 0.05;
            }, 500);
        }
    }

    function lossBurst() {
        // Flash red
        if (scene) {
            const flash = new THREE.PointLight(0xff0000, 3, 20);
            flash.position.set(0, 2, 3);
            scene.add(flash);
            setTimeout(() => scene.remove(flash), 600);
        }
    }

    // ==================== SCREENS ====================
    function showScreen(id) {
        document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
        const el = document.getElementById(id);
        if (el) el.classList.add('active');
    }

    function showModal(id) {
        const el = document.getElementById(id);
        if (el) el.classList.remove('hidden');
    }

    function hideModal(id) {
        const el = document.getElementById(id);
        if (el) el.classList.add('hidden');
    }

    function showToast(msg, duration = 3000) {
        const toast = document.getElementById('toast');
        const msgEl = document.getElementById('toast-message');
        if (!toast || !msgEl) return;
        msgEl.textContent = msg;
        toast.classList.remove('hidden');
        clearTimeout(toast._timeout);
        toast._timeout = setTimeout(() => toast.classList.add('hidden'), duration);
    }

    // ==================== COUNTRY PICKER ====================
    const COUNTRIES = [
        {name:'Ghana',code:'+233',iso:'GH',flag:'🇬🇭'},{name:'Nigeria',code:'+234',iso:'NG',flag:'🇳🇬'},
        {name:'Kenya',code:'+254',iso:'KE',flag:'🇰🇪'},{name:'South Africa',code:'+27',iso:'ZA',flag:'🇿🇦'},
        {name:'Uganda',code:'+256',iso:'UG',flag:'🇺🇬'},{name:'Tanzania',code:'+255',iso:'TZ',flag:'🇹🇿'},
        {name:'Cameroon',code:'+237',iso:'CM',flag:'🇨🇲'},{name:'Ivory Coast',code:'+225',iso:'CI',flag:'🇨🇮'},
        {name:'Senegal',code:'+221',iso:'SN',flag:'🇸🇳'},{name:'Rwanda',code:'+250',iso:'RW',flag:'🇷🇼'},
        {name:'Ethiopia',code:'+251',iso:'ET',flag:'🇪🇹'},{name:'Zambia',code:'+260',iso:'ZM',flag:'🇿🇲'},
        {name:'Zimbabwe',code:'+263',iso:'ZW',flag:'🇿🇼'},{name:'Mozambique',code:'+258',iso:'MZ',flag:'🇲🇿'},
        {name:'Botswana',code:'+267',iso:'BW',flag:'🇧🇼'},{name:'Namibia',code:'+264',iso:'NA',flag:'🇳🇦'},
        {name:'Malawi',code:'+265',iso:'MW',flag:'🇲🇼'},{name:'Mali',code:'+223',iso:'ML',flag:'🇲🇱'},
        {name:'Burkina Faso',code:'+226',iso:'BF',flag:'🇧🇫'},{name:'Niger',code:'+227',iso:'NE',flag:'🇳🇪'},
        {name:'Togo',code:'+228',iso:'TG',flag:'🇹🇬'},{name:'Benin',code:'+229',iso:'BJ',flag:'🇧🇯'},
        {name:'Sierra Leone',code:'+232',iso:'SL',flag:'🇸🇱'},{name:'Liberia',code:'+231',iso:'LR',flag:'🇱🇷'},
        {name:'Gambia',code:'+220',iso:'GM',flag:'🇬🇲'},{name:'Guinea',code:'+224',iso:'GN',flag:'🇬🇳'},
        {name:'DR Congo',code:'+243',iso:'CD',flag:'🇨🇩'},{name:'Congo',code:'+242',iso:'CG',flag:'🇨🇬'},
        {name:'Angola',code:'+244',iso:'AO',flag:'🇦🇴'},{name:'Gabon',code:'+241',iso:'GA',flag:'🇬🇦'},
        {name:'Chad',code:'+235',iso:'TD',flag:'🇹🇩'},{name:'Madagascar',code:'+261',iso:'MG',flag:'🇲🇬'},
        {name:'Mauritius',code:'+230',iso:'MU',flag:'🇲🇺'},{name:'Somalia',code:'+252',iso:'SO',flag:'🇸🇴'},
        {name:'Sudan',code:'+249',iso:'SD',flag:'🇸🇩'},{name:'South Sudan',code:'+211',iso:'SS',flag:'🇸🇸'},
        {name:'Egypt',code:'+20',iso:'EG',flag:'🇪🇬'},{name:'Morocco',code:'+212',iso:'MA',flag:'🇲🇦'},
        {name:'Tunisia',code:'+216',iso:'TN',flag:'🇹🇳'},{name:'Algeria',code:'+213',iso:'DZ',flag:'🇩🇿'},
        {name:'Libya',code:'+218',iso:'LY',flag:'🇱🇾'},{name:'Eritrea',code:'+291',iso:'ER',flag:'🇪🇷'},
        {name:'Djibouti',code:'+253',iso:'DJ',flag:'🇩🇯'},{name:'Comoros',code:'+269',iso:'KM',flag:'🇰🇲'},
        {name:'Cabo Verde',code:'+238',iso:'CV',flag:'🇨🇻'},{name:'Eswatini',code:'+268',iso:'SZ',flag:'🇸🇿'},
        {name:'Lesotho',code:'+266',iso:'LS',flag:'🇱🇸'},{name:'Equatorial Guinea',code:'+240',iso:'GQ',flag:'🇬🇶'},
        {name:'Guinea-Bissau',code:'+245',iso:'GW',flag:'🇬🇼'},{name:'Central African Rep.',code:'+236',iso:'CF',flag:'🇨🇫'},
        {name:'Mauritania',code:'+222',iso:'MR',flag:'🇲🇷'},{name:'Burundi',code:'+257',iso:'BI',flag:'🇧🇮'},
        {name:'Seychelles',code:'+248',iso:'SC',flag:'🇸🇨'},{name:'São Tomé',code:'+239',iso:'ST',flag:'🇸🇹'},
        {name:'United Kingdom',code:'+44',iso:'GB',flag:'🇬🇧'},{name:'United States',code:'+1',iso:'US',flag:'🇺🇸'},
        {name:'Canada',code:'+1',iso:'CA',flag:'🇨🇦'},{name:'France',code:'+33',iso:'FR',flag:'🇫🇷'},
        {name:'Germany',code:'+49',iso:'DE',flag:'🇩🇪'},{name:'Italy',code:'+39',iso:'IT',flag:'🇮🇹'},
        {name:'Spain',code:'+34',iso:'ES',flag:'🇪🇸'},{name:'Portugal',code:'+351',iso:'PT',flag:'🇵🇹'},
        {name:'Netherlands',code:'+31',iso:'NL',flag:'🇳🇱'},{name:'Belgium',code:'+32',iso:'BE',flag:'🇧🇪'},
        {name:'Switzerland',code:'+41',iso:'CH',flag:'🇨🇭'},{name:'Austria',code:'+43',iso:'AT',flag:'🇦🇹'},
        {name:'Sweden',code:'+46',iso:'SE',flag:'🇸🇪'},{name:'Norway',code:'+47',iso:'NO',flag:'🇳🇴'},
        {name:'Denmark',code:'+45',iso:'DK',flag:'🇩🇰'},{name:'Finland',code:'+358',iso:'FI',flag:'🇫🇮'},
        {name:'Ireland',code:'+353',iso:'IE',flag:'🇮🇪'},{name:'Poland',code:'+48',iso:'PL',flag:'🇵🇱'},
        {name:'Czech Republic',code:'+420',iso:'CZ',flag:'🇨🇿'},{name:'Romania',code:'+40',iso:'RO',flag:'🇷🇴'},
        {name:'Hungary',code:'+36',iso:'HU',flag:'🇭🇺'},{name:'Greece',code:'+30',iso:'GR',flag:'🇬🇷'},
        {name:'Turkey',code:'+90',iso:'TR',flag:'🇹🇷'},{name:'Russia',code:'+7',iso:'RU',flag:'🇷🇺'},
        {name:'Ukraine',code:'+380',iso:'UA',flag:'🇺🇦'},{name:'India',code:'+91',iso:'IN',flag:'🇮🇳'},
        {name:'Pakistan',code:'+92',iso:'PK',flag:'🇵🇰'},{name:'Bangladesh',code:'+880',iso:'BD',flag:'🇧🇩'},
        {name:'Sri Lanka',code:'+94',iso:'LK',flag:'🇱🇰'},{name:'Nepal',code:'+977',iso:'NP',flag:'🇳🇵'},
        {name:'China',code:'+86',iso:'CN',flag:'🇨🇳'},{name:'Japan',code:'+81',iso:'JP',flag:'🇯🇵'},
        {name:'South Korea',code:'+82',iso:'KR',flag:'🇰🇷'},{name:'Philippines',code:'+63',iso:'PH',flag:'🇵🇭'},
        {name:'Indonesia',code:'+62',iso:'ID',flag:'🇮🇩'},{name:'Malaysia',code:'+60',iso:'MY',flag:'🇲🇾'},
        {name:'Thailand',code:'+66',iso:'TH',flag:'🇹🇭'},{name:'Vietnam',code:'+84',iso:'VN',flag:'🇻🇳'},
        {name:'Singapore',code:'+65',iso:'SG',flag:'🇸🇬'},{name:'Australia',code:'+61',iso:'AU',flag:'🇦🇺'},
        {name:'New Zealand',code:'+64',iso:'NZ',flag:'🇳🇿'},{name:'Brazil',code:'+55',iso:'BR',flag:'🇧🇷'},
        {name:'Mexico',code:'+52',iso:'MX',flag:'🇲🇽'},{name:'Argentina',code:'+54',iso:'AR',flag:'🇦🇷'},
        {name:'Colombia',code:'+57',iso:'CO',flag:'🇨🇴'},{name:'Chile',code:'+56',iso:'CL',flag:'🇨🇱'},
        {name:'Peru',code:'+51',iso:'PE',flag:'🇵🇪'},{name:'Saudi Arabia',code:'+966',iso:'SA',flag:'🇸🇦'},
        {name:'UAE',code:'+971',iso:'AE',flag:'🇦🇪'},{name:'Qatar',code:'+974',iso:'QA',flag:'🇶🇦'},
        {name:'Kuwait',code:'+965',iso:'KW',flag:'🇰🇼'},{name:'Bahrain',code:'+973',iso:'BH',flag:'🇧🇭'},
        {name:'Oman',code:'+968',iso:'OM',flag:'🇴🇲'},{name:'Jordan',code:'+962',iso:'JO',flag:'🇯🇴'},
        {name:'Lebanon',code:'+961',iso:'LB',flag:'🇱🇧'},{name:'Israel',code:'+972',iso:'IL',flag:'🇮🇱'},
        {name:'Jamaica',code:'+1876',iso:'JM',flag:'🇯🇲'},{name:'Trinidad',code:'+1868',iso:'TT',flag:'🇹🇹'},
        {name:'Barbados',code:'+1246',iso:'BB',flag:'🇧🇧'},{name:'Haiti',code:'+509',iso:'HT',flag:'🇭🇹'},
        {name:'Cuba',code:'+53',iso:'CU',flag:'🇨🇺'},{name:'Dominican Rep.',code:'+1809',iso:'DO',flag:'🇩🇴'},
    ];

    let selectedCountry = COUNTRIES[0]; // Ghana default

    function initCountryPicker() {
        const toggle = document.getElementById('country-toggle');
        const dropdown = document.getElementById('country-dropdown');
        const search = document.getElementById('country-search');
        const list = document.getElementById('country-list');
        if (!toggle || !dropdown || !list) return;

        function renderList(filter) {
            const q = (filter || '').toLowerCase();
            const filtered = q ? COUNTRIES.filter(c =>
                c.name.toLowerCase().includes(q) || c.code.includes(q) || c.iso.toLowerCase().includes(q)
            ) : COUNTRIES;
            list.innerHTML = filtered.map(c =>
                `<div class="country-item${c.iso === selectedCountry.iso ? ' active' : ''}" data-iso="${c.iso}">` +
                `<span class="ci-flag">${c.flag}</span>` +
                `<span class="ci-name">${c.name}</span>` +
                `<span class="ci-code">${c.code}</span></div>`
            ).join('');
        }

        function selectCountry(c) {
            selectedCountry = c;
            document.getElementById('selected-flag').textContent = c.flag;
            document.getElementById('selected-code').textContent = c.code;
            dropdown.classList.add('hidden');
            search.value = '';
            renderList('');
            document.getElementById('phone-input')?.focus();
        }

        renderList('');

        // Set initial flag via JS to ensure emoji renders
        document.getElementById('selected-flag').textContent = selectedCountry.flag;
        document.getElementById('selected-code').textContent = selectedCountry.code;

        toggle.addEventListener('click', (e) => {
            e.preventDefault();
            dropdown.classList.toggle('hidden');
            if (!dropdown.classList.contains('hidden')) {
                search.value = '';
                renderList('');
                setTimeout(() => search.focus(), 50);
            }
        });

        search.addEventListener('input', () => renderList(search.value));

        list.addEventListener('click', (e) => {
            const item = e.target.closest('.country-item');
            if (!item) return;
            const iso = item.dataset.iso;
            const c = COUNTRIES.find(x => x.iso === iso);
            if (c) selectCountry(c);
        });

        // Close dropdown on outside click
        document.addEventListener('click', (e) => {
            if (!e.target.closest('#country-picker')) {
                dropdown.classList.add('hidden');
            }
        });

        // Keyboard nav in search
        search.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') dropdown.classList.add('hidden');
            if (e.key === 'Enter') {
                const first = list.querySelector('.country-item');
                if (first) {
                    const iso = first.dataset.iso;
                    const c = COUNTRIES.find(x => x.iso === iso);
                    if (c) selectCountry(c);
                }
            }
        });
    }

    // ==================== AUTH ====================
    function initAuth() {
        initCountryPicker();
        // Fetch auth methods config from admin
        fetch(API.base + '/accounts/auth/methods/')
            .then(r => r.json())
            .then(methods => {
                // OTP channels
                const smsBtn = document.querySelector('.channel-btn[data-channel="sms"]');
                const waBtn = document.querySelector('.channel-btn[data-channel="whatsapp"]');
                if (smsBtn && !methods.sms_otp) smsBtn.style.display = 'none';
                if (waBtn && !methods.whatsapp_otp) waBtn.style.display = 'none';
                // If only one channel available, auto-select it
                if (methods.sms_otp && !methods.whatsapp_otp && smsBtn) {
                    smsBtn.classList.add('active');
                    state.otpChannel = 'sms';
                } else if (!methods.sms_otp && methods.whatsapp_otp && waBtn) {
                    waBtn.classList.add('active');
                    state.otpChannel = 'whatsapp';
                }
                // Social login buttons
                let anySocial = false;
                if (methods.google) {
                    const g = document.getElementById('btn-google');
                    if (g) g.style.display = '';
                    anySocial = true;
                }
                if (methods.facebook) {
                    const f = document.getElementById('btn-facebook');
                    if (f) f.style.display = '';
                    anySocial = true;
                }
                if (anySocial) {
                    const div = document.getElementById('social-divider');
                    const btns = document.getElementById('social-buttons');
                    if (div) div.style.display = '';
                    if (btns) btns.style.display = '';
                }
            })
            .catch(() => {}); // Fail silently — buttons stay hidden

        // Channel buttons
        document.querySelectorAll('.channel-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.channel-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                state.otpChannel = btn.dataset.channel;
            });
        });

        // Send OTP
        document.getElementById('send-otp-btn')?.addEventListener('click', async () => {
            const rawPhone = document.getElementById('phone-input')?.value?.trim();
            if (!rawPhone || rawPhone.length < 7) {
                showError('Enter a valid phone number');
                return;
            }

            // Build full phone: country code + local number (strip leading 0)
            const countryCode = selectedCountry.code || '+233';
            let local = rawPhone.replace(/[\s\-]/g, '');
            if (local.startsWith('0')) local = local.substring(1);
            const phone = countryCode + local;

            const btn = document.getElementById('send-otp-btn');
            btn.disabled = true;
            btn.textContent = 'Sending...';

            try {
                const resp = await fetch(API.base + '/accounts/auth/request-otp/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ phone, channel: state.otpChannel }),
                });
                const data = await resp.json();

                if (resp.ok) {
                    state.otpPhone = phone;
                    document.getElementById('otp-phone-display').textContent = phone;
                    document.getElementById('otp-step-1').classList.remove('active');
                    document.getElementById('otp-step-2').classList.add('active');
                    showError('');
                    // Focus first OTP input
                    document.querySelector('.otp-digit[data-index="0"]')?.focus();
                } else {
                    showError(data.error || 'Failed to send OTP');
                }
            } catch (e) {
                showError('Network error. Try again.');
            }

            btn.disabled = false;
            btn.textContent = 'Send Code';
        });

        // OTP digit inputs
        document.querySelectorAll('.otp-digit').forEach(input => {
            input.addEventListener('input', (e) => {
                const idx = parseInt(input.dataset.index);
                if (input.value && idx < 5) {
                    document.querySelector(`.otp-digit[data-index="${idx + 1}"]`)?.focus();
                }
                // Auto-verify when all filled
                const code = getOTPCode();
                if (code.length === 6) {
                    verifyOTP();
                }
            });
            input.addEventListener('keydown', (e) => {
                const idx = parseInt(input.dataset.index);
                if (e.key === 'Backspace' && !input.value && idx > 0) {
                    document.querySelector(`.otp-digit[data-index="${idx - 1}"]`)?.focus();
                }
            });
        });

        // Verify button
        document.getElementById('verify-otp-btn')?.addEventListener('click', verifyOTP);

        // Back button
        document.getElementById('back-to-phone')?.addEventListener('click', () => {
            document.getElementById('otp-step-2').classList.remove('active');
            document.getElementById('otp-step-1').classList.add('active');
            document.querySelectorAll('.otp-digit').forEach(d => d.value = '');
        });
    }

    function getOTPCode() {
        return Array.from(document.querySelectorAll('.otp-digit')).map(d => d.value).join('');
    }

    async function verifyOTP() {
        const code = getOTPCode();
        if (code.length !== 6) { showError('Enter all 6 digits'); return; }

        const btn = document.getElementById('verify-otp-btn');
        btn.disabled = true;
        btn.textContent = 'Verifying...';

        try {
            const body = { phone: state.otpPhone, code };
            if (state.refCode) body.ref_code = state.refCode;

            const resp = await fetch(API.base + '/accounts/auth/verify-otp/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await resp.json();

            if (resp.ok) {
                state.token = data.access_token;
                state.refreshToken = data.refresh_token;
                state.player = data.player;
                localStorage.setItem('cf_access_token', data.access_token);
                localStorage.setItem('cf_refresh_token', data.refresh_token);
                scheduleTokenRefresh();
                showError('');
                enterLobby();
            } else {
                showError(data.error || 'Invalid OTP');
            }
        } catch (e) {
            showError('Network error. Try again.');
        }

        btn.disabled = false;
        btn.textContent = 'Verify';
    }

    function showError(msg) {
        const el = document.getElementById('auth-error');
        if (el) el.textContent = msg;
    }

    function logout() {
        state.token = null;
        state.refreshToken = null;
        state.player = null;
        state.session = null;
        if (refreshTimer) clearTimeout(refreshTimer);
        localStorage.removeItem('cf_access_token');
        localStorage.removeItem('cf_refresh_token');
        showScreen('auth-screen');
    }

    // ==================== LOBBY ====================
    async function enterLobby() {
        showScreen('lobby-screen');
        await Promise.all([loadProfile(), loadWalletBalance()]);
        checkActiveSession();
    }

    async function loadProfile() {
        try {
            const resp = await API.get('/accounts/profile/');
            if (resp.ok) {
                state.player = await resp.json();
                updateLobbyUI();
            }
        } catch (e) { console.error('Profile load error:', e); }
    }

    async function loadWalletBalance() {
        try {
            const resp = await API.get('/payments/wallet/');
            if (resp.ok) {
                const data = await resp.json();
                document.getElementById('lobby-balance').textContent =
                    `${data.currency_symbol}${parseFloat(data.balance).toFixed(2)}`;
            }
        } catch (e) { console.error('Wallet load error:', e); }
    }

    function updateLobbyUI() {
        if (!state.player) return;
        const name = state.player.display_name || state.player.phone || 'Player';
        document.getElementById('lobby-player-name').textContent = name;
        document.getElementById('profile-name').textContent = name;
        document.getElementById('profile-phone').textContent = state.player.phone || '';

        if (state.player.profile) {
            const p = state.player.profile;
            document.getElementById('stat-games').textContent = p.total_games || 0;
            document.getElementById('stat-wins').textContent = p.total_won || 0;
            document.getElementById('stat-losses').textContent = p.total_lost || 0;
            document.getElementById('stat-highest').textContent = `₵${parseFloat(p.highest_cashout || 0).toFixed(2)}`;
        }
    }

    async function checkActiveSession() {
        try {
            const resp = await API.get('/game/state/');
            if (resp.ok) {
                const data = await resp.json();
                if (data.active_session) {
                    state.session = data.session;
                    enterGame();
                }
            }
        } catch (e) { console.error('Session check error:', e); }
    }

    // ==================== GAME ====================
    async function startGame() {
        const stakeInput = document.getElementById('stake-input');
        const stake = parseFloat(stakeInput?.value || '1');

        if (isNaN(stake) || stake < 0.5) {
            showToast('Enter a valid stake amount');
            return;
        }

        const btn = document.getElementById('start-game-btn');
        btn.disabled = true;
        btn.textContent = 'Starting...';

        try {
            const resp = await API.post('/game/start/', {
                stake_amount: stake.toFixed(2),
                currency_code: 'GHS',
            });
            const data = await resp.json();

            if (resp.ok) {
                state.session = {
                    id: data.session_id,
                    server_seed_hash: data.server_seed_hash,
                    stake_amount: data.stake_amount,
                    cashout_balance: '0.00',
                    flip_count: 0,
                    status: 'active',
                    currency: data.currency,
                };
                enterGame();
            } else {
                showToast(data.error || 'Failed to start game');
            }
        } catch (e) {
            showToast('Network error');
        }

        btn.disabled = false;
        btn.textContent = '🎰 FLIP NOW';
    }

    function enterGame() {
        showScreen('game-screen');
        initScene();
        updateGameHUD();

        document.getElementById('flip-btn').disabled = false;
        document.getElementById('pause-btn').disabled = false;
    }

    function updateGameHUD() {
        if (!state.session) return;
        const s = state.session;
        const sym = s.currency?.symbol || 'GH₵';

        document.getElementById('hud-stake').textContent = `${sym}${parseFloat(s.stake_amount).toFixed(2)}`;
        document.getElementById('hud-flips').textContent = s.flip_count || 0;

        const cashout = parseFloat(s.cashout_balance || 0);
        document.getElementById('hud-cashout').textContent = `${sym}${cashout.toFixed(2)}`;
        document.getElementById('cashout-btn').disabled = cashout <= 0;
    }

    async function doFlip() {
        if (state.isFlipping || !state.session) return;

        const flipBtn = document.getElementById('flip-btn');
        flipBtn.disabled = true;

        try {
            const resp = await API.post('/game/flip/', {});
            const data = await resp.json();

            if (!data.success) {
                showToast(data.error || 'Flip failed');
                flipBtn.disabled = false;
                return;
            }

            // Animate the flip
            await flipAnimation(data.is_zero, data.value);

            // Update session state
            state.session.flip_count = data.flip_number;
            state.session.cashout_balance = data.cashout_balance;

            if (data.is_zero) {
                // LOSS
                state.session.status = 'lost';
                lossBurst();

                document.getElementById('loss-stake-amount').textContent =
                    `${state.session.currency?.symbol || 'GH₵'}${parseFloat(state.session.stake_amount).toFixed(2)}`;
                document.getElementById('loss-overlay').classList.remove('hidden');
            } else {
                // WIN - show denomination
                const denomDisplay = document.getElementById('denom-display');
                const denomValue = document.getElementById('denom-value');
                const sym = state.session.currency?.symbol || 'GH₵';
                denomValue.textContent = `+${sym}${parseFloat(data.value).toFixed(2)}`;
                denomDisplay.classList.add('show');

                winCelebration();

                // Show quick result overlay
                const resultOverlay = document.getElementById('flip-result-overlay');
                document.getElementById('result-icon').textContent = '💵';
                document.getElementById('result-value').textContent = `+${sym}${parseFloat(data.value).toFixed(2)}`;
                document.getElementById('result-balance').textContent =
                    `Balance: ${sym}${parseFloat(data.cashout_balance).toFixed(2)}`;
                resultOverlay.classList.remove('hidden');

                setTimeout(() => {
                    resultOverlay.classList.add('hidden');
                    denomDisplay.classList.remove('show');
                }, 1000);

                updateGameHUD();
                flipBtn.disabled = false;

                // Check for ad
                if (data.ad_due) {
                    showAd();
                }
            }
        } catch (e) {
            showToast('Network error');
            flipBtn.disabled = false;
        }
    }

    async function doCashout() {
        if (!state.session || state.isFlipping) return;

        const btn = document.getElementById('cashout-btn');
        btn.disabled = true;

        try {
            const resp = await API.post('/game/cashout/', {});
            const data = await resp.json();

            if (resp.ok) {
                state.session.status = 'cashed_out';
                const sym = state.session.currency?.symbol || 'GH₵';
                document.getElementById('cashout-total').textContent =
                    `${sym}${parseFloat(data.cashout_amount).toFixed(2)}`;
                document.getElementById('cashout-overlay').classList.remove('hidden');
                winCelebration();
            } else {
                showToast(data.error || 'Cashout failed');
                btn.disabled = false;
            }
        } catch (e) {
            showToast('Network error');
            btn.disabled = false;
        }
    }

    async function doPause() {
        if (!state.session) return;

        // First get pause cost
        try {
            const resp = await API.post('/game/pause/', { confirm: false });
            const data = await resp.json();

            const sym = state.session.currency?.symbol || 'GH₵';
            document.getElementById('pause-balance-display').textContent =
                `${sym}${parseFloat(data.current_balance || state.session.cashout_balance).toFixed(2)}`;
            document.getElementById('pause-fee-display').textContent =
                `${sym}${parseFloat(data.pause_cost || 0).toFixed(2)}`;
            document.getElementById('pause-after-display').textContent =
                `${sym}${parseFloat(data.balance_after_pause || 0).toFixed(2)}`;

            showModal('pause-modal');
        } catch (e) {
            showToast('Network error');
        }
    }

    async function confirmPause() {
        try {
            const resp = await API.post('/game/pause/', { confirm: true });
            const data = await resp.json();

            if (resp.ok) {
                hideModal('pause-modal');
                state.session.status = 'paused';
                showToast('Game paused. You can resume later.');
                returnToLobby();
            } else {
                showToast(data.error || 'Pause failed');
            }
        } catch (e) {
            showToast('Network error');
        }
    }

    function returnToLobby() {
        if (animationId) cancelAnimationFrame(animationId);
        state.session = null;
        document.getElementById('loss-overlay')?.classList.add('hidden');
        document.getElementById('cashout-overlay')?.classList.add('hidden');
        document.getElementById('flip-result-overlay')?.classList.add('hidden');
        enterLobby();
    }

    // ==================== ADS ====================
    function showAd() {
        // Placeholder - in production this would fetch from /api/ads/next/
        const adOverlay = document.getElementById('ad-overlay');
        const adContent = document.getElementById('ad-content');
        const skipBtn = document.getElementById('ad-skip-btn');
        const timerText = document.getElementById('ad-timer-text');

        adContent.innerHTML = '<div style="width:280px;height:150px;background:linear-gradient(135deg,#1a1a2e,#16213e);display:flex;align-items:center;justify-content:center;border-radius:8px;color:#ffd700;font-family:Orbitron,sans-serif;">Ad Space</div>';
        adOverlay.classList.remove('hidden');
        skipBtn.classList.add('hidden');

        let countdown = 5;
        timerText.textContent = `Skip in ${countdown}s`;

        const timer = setInterval(() => {
            countdown--;
            if (countdown <= 0) {
                clearInterval(timer);
                skipBtn.classList.remove('hidden');
                timerText.textContent = '';
            } else {
                timerText.textContent = `Skip in ${countdown}s`;
            }
        }, 1000);

        skipBtn.onclick = () => {
            adOverlay.classList.add('hidden');
            clearInterval(timer);
        };
    }

    // ==================== PAYMENTS ====================

    // Client-side network detection from phone prefix (Ghana numbers)
    const NETWORK_PREFIXES = {
        '023': 'MTN', '024': 'MTN', '054': 'MTN', '055': 'MTN', '059': 'MTN',
        '020': 'VOD', '050': 'VOD',
        '027': 'AIR', '057': 'AIR', '026': 'AIR', '056': 'AIR',
    };
    const NETWORK_NAMES = { MTN: 'MTN Mobile Money', VOD: 'Telecel Cash', AIR: 'AirtelTigo Money' };

    function detectNetworkFromPhone(phone) {
        const cleaned = phone.replace(/\D/g, '');
        const prefix3 = cleaned.substring(0, 3);
        return NETWORK_PREFIXES[prefix3] || null;
    }

    let _verifyTimeout = null;
    let _lastVerifiedPhone = '';

    function resetDepositVerification() {
        const btn = document.getElementById('dep-momo-btn');
        const verifyStatus = document.getElementById('dep-verify-status');
        const verifiedInfo = document.getElementById('dep-verified-info');
        if (btn) btn.disabled = true;
        if (verifyStatus) verifyStatus.style.display = 'none';
        if (verifiedInfo) verifiedInfo.style.display = 'none';
        document.getElementById('dep-account-id').value = '';
        _lastVerifiedPhone = '';
    }

    function handleDepPhoneInput() {
        const phoneEl = document.getElementById('dep-phone');
        const networkLabel = document.getElementById('dep-network-label');
        const networkHidden = document.getElementById('dep-network');
        const phone = phoneEl.value.replace(/\D/g, '');

        // Auto-detect network from prefix
        const nw = detectNetworkFromPhone(phone);
        if (nw && phone.length >= 3) {
            networkLabel.textContent = NETWORK_NAMES[nw] || nw;
            networkLabel.className = 'network-badge ' + nw.toLowerCase();
            networkLabel.style.display = 'inline-block';
            networkHidden.value = nw;
        } else {
            networkLabel.style.display = 'none';
            networkHidden.value = '';
        }

        // Reset verification if phone changed
        if (phone !== _lastVerifiedPhone) {
            resetDepositVerification();
        }

        // Auto-verify when 10 digits entered
        if (_verifyTimeout) clearTimeout(_verifyTimeout);
        if (phone.length === 10 && nw && phone !== _lastVerifiedPhone) {
            _verifyTimeout = setTimeout(() => verifyDepositPhone(phone), 400);
        }
    }

    async function verifyDepositPhone(phone) {
        const verifyStatus = document.getElementById('dep-verify-status');
        const spinner = document.getElementById('dep-verify-spinner');
        const verifyText = document.getElementById('dep-verify-text');
        const verifiedInfo = document.getElementById('dep-verified-info');
        const verifiedName = document.getElementById('dep-verified-name');
        const btn = document.getElementById('dep-momo-btn');

        // Show verifying state
        verifyStatus.style.display = 'flex';
        verifyStatus.className = 'verify-status';
        spinner.style.display = 'inline-block';
        verifyText.textContent = 'Verifying account...';
        verifiedInfo.style.display = 'none';
        btn.disabled = true;

        try {
            const resp = await API.post('/payments/momo-accounts/add/', {
                mobile_number: phone,
            });
            const data = await resp.json();

            if (data.success && data.account) {
                spinner.style.display = 'none';
                verifyStatus.style.display = 'none';
                verifiedInfo.style.display = 'block';
                verifiedName.textContent = `${data.account.verified_name} (${NETWORK_NAMES[data.account.network] || data.account.network})`;
                document.getElementById('dep-account-id').value = data.account.id;
                document.getElementById('dep-network').value = data.account.network;
                btn.disabled = false;
                _lastVerifiedPhone = phone;
            } else {
                spinner.style.display = 'none';
                verifyText.textContent = data.error || 'Verification failed';
                verifyStatus.className = 'verify-status error';
            }
        } catch (e) {
            spinner.style.display = 'none';
            verifyText.textContent = 'Could not verify. Check number and try again.';
            verifyStatus.className = 'verify-status error';
        }
    }

    async function depositMoMo() {
        const amount = document.getElementById('dep-amount')?.value;
        const accountId = document.getElementById('dep-account-id')?.value;
        const statusEl = document.getElementById('dep-status');

        if (!amount) {
            statusEl.textContent = 'Enter an amount';
            statusEl.className = 'status-msg error';
            return;
        }
        if (!accountId) {
            statusEl.textContent = 'Enter your mobile number and wait for verification';
            statusEl.className = 'status-msg error';
            return;
        }

        statusEl.textContent = 'Sending payment prompt...';
        statusEl.className = 'status-msg';

        try {
            const resp = await API.post('/payments/deposit/mobile-money/', {
                amount, account_id: accountId,
            });
            const data = await resp.json();

            if (data.success) {
                statusEl.textContent = `Payment prompt sent to ${data.verified_name || 'your phone'}! Check your phone.`;
                statusEl.className = 'status-msg success';
                setTimeout(() => {
                    hideModal('deposit-modal');
                    loadWalletBalance();
                }, 3000);
            } else {
                statusEl.textContent = data.error || 'Deposit failed';
                statusEl.className = 'status-msg error';
            }
        } catch (e) {
            statusEl.textContent = 'Network error';
            statusEl.className = 'status-msg error';
        }
    }

    async function depositCard() {
        const amount = document.getElementById('dep-card-amount')?.value;
        const statusEl = document.getElementById('dep-status');

        if (!amount) {
            statusEl.textContent = 'Enter an amount';
            statusEl.className = 'status-msg error';
            return;
        }

        statusEl.textContent = 'Redirecting to payment...';
        statusEl.className = 'status-msg';

        try {
            const resp = await API.post('/payments/deposit/card/', { amount });
            const data = await resp.json();

            if (data.success && data.authorization_url) {
                window.open(data.authorization_url, '_blank');
                statusEl.textContent = 'Complete payment in the new tab.';
                statusEl.className = 'status-msg success';
            } else {
                statusEl.textContent = data.error || 'Card payment failed';
                statusEl.className = 'status-msg error';
            }
        } catch (e) {
            statusEl.textContent = 'Network error';
            statusEl.className = 'status-msg error';
        }
    }

    // Withdraw phone input handler (same network detect + verify pattern)
    let _wdrVerifyTimeout = null;
    let _wdrLastVerifiedPhone = '';

    function resetWithdrawVerification() {
        const btn = document.getElementById('wdr-btn');
        const verifyStatus = document.getElementById('wdr-verify-status');
        const verifiedInfo = document.getElementById('wdr-verified-info');
        if (btn) btn.disabled = true;
        if (verifyStatus) verifyStatus.style.display = 'none';
        if (verifiedInfo) verifiedInfo.style.display = 'none';
        document.getElementById('wdr-account-id').value = '';
        _wdrLastVerifiedPhone = '';
    }

    function handleWdrPhoneInput() {
        const phoneEl = document.getElementById('wdr-phone');
        const networkLabel = document.getElementById('wdr-network-label');
        const networkHidden = document.getElementById('wdr-network');
        const phone = phoneEl.value.replace(/\D/g, '');

        const nw = detectNetworkFromPhone(phone);
        if (nw && phone.length >= 3) {
            networkLabel.textContent = NETWORK_NAMES[nw] || nw;
            networkLabel.className = 'network-badge ' + nw.toLowerCase();
            networkLabel.style.display = 'inline-block';
            networkHidden.value = nw;
        } else {
            networkLabel.style.display = 'none';
            networkHidden.value = '';
        }

        if (phone !== _wdrLastVerifiedPhone) {
            resetWithdrawVerification();
        }

        if (_wdrVerifyTimeout) clearTimeout(_wdrVerifyTimeout);
        if (phone.length === 10 && nw && phone !== _wdrLastVerifiedPhone) {
            _wdrVerifyTimeout = setTimeout(() => verifyWithdrawPhone(phone), 400);
        }
    }

    async function verifyWithdrawPhone(phone) {
        const verifyStatus = document.getElementById('wdr-verify-status');
        const spinner = document.getElementById('wdr-verify-spinner');
        const verifyText = document.getElementById('wdr-verify-text');
        const verifiedInfo = document.getElementById('wdr-verified-info');
        const verifiedName = document.getElementById('wdr-verified-name');
        const btn = document.getElementById('wdr-btn');

        verifyStatus.style.display = 'flex';
        verifyStatus.className = 'verify-status';
        spinner.style.display = 'inline-block';
        verifyText.textContent = 'Verifying account...';
        verifiedInfo.style.display = 'none';
        btn.disabled = true;

        try {
            const resp = await API.post('/payments/momo-accounts/add/', {
                mobile_number: phone,
            });
            const data = await resp.json();

            if (data.success && data.account) {
                spinner.style.display = 'none';
                verifyStatus.style.display = 'none';
                verifiedInfo.style.display = 'block';
                verifiedName.textContent = `${data.account.verified_name} (${NETWORK_NAMES[data.account.network] || data.account.network})`;
                document.getElementById('wdr-account-id').value = data.account.id;
                document.getElementById('wdr-network').value = data.account.network;
                btn.disabled = false;
                _wdrLastVerifiedPhone = phone;
            } else {
                spinner.style.display = 'none';
                verifyText.textContent = data.error || 'Verification failed';
                verifyStatus.className = 'verify-status error';
            }
        } catch (e) {
            spinner.style.display = 'none';
            verifyText.textContent = 'Could not verify. Check number and try again.';
            verifyStatus.className = 'verify-status error';
        }
    }

    async function doWithdraw() {
        const amount = document.getElementById('wdr-amount')?.value;
        const accountId = document.getElementById('wdr-account-id')?.value;
        const statusEl = document.getElementById('wdr-status');

        if (!amount) {
            statusEl.textContent = 'Enter an amount';
            statusEl.className = 'status-msg error';
            return;
        }
        if (!accountId) {
            statusEl.textContent = 'Enter your mobile number and wait for verification';
            statusEl.className = 'status-msg error';
            return;
        }

        statusEl.textContent = 'Processing withdrawal...';
        statusEl.className = 'status-msg';

        try {
            const resp = await API.post('/payments/withdraw/', {
                amount, account_id: accountId,
            });
            const data = await resp.json();

            if (data.success) {
                statusEl.textContent = 'Withdrawal processing! Funds will arrive shortly.';
                statusEl.className = 'status-msg success';
                setTimeout(() => {
                    hideModal('withdraw-modal');
                    loadWalletBalance();
                }, 3000);
            } else {
                statusEl.textContent = data.error || 'Withdrawal failed';
                statusEl.className = 'status-msg error';
            }
        } catch (e) {
            statusEl.textContent = 'Network error';
            statusEl.className = 'status-msg error';
        }
    }

    // ==================== HISTORY & REFERRAL ====================
    async function loadHistory() {
        const container = document.getElementById('history-list');
        if (!container) return;

        try {
            const resp = await API.get('/game/history/');
            if (resp.ok) {
                const sessions = await resp.json();
                if (sessions.length === 0) {
                    container.innerHTML = '<p class="text-muted">No games yet. Start playing!</p>';
                    return;
                }
                container.innerHTML = sessions.map(s => {
                    const sym = s.currency?.symbol || 'GH₵';
                    const statusClass = s.status === 'cashed_out' ? 'won' : 'lost';
                    const statusText = s.status === 'cashed_out' ? `Won ${sym}${parseFloat(s.cashout_balance).toFixed(2)}` : 'Lost';
                    const date = new Date(s.created_at).toLocaleDateString();
                    return `<div class="history-item">
                        <div>
                            <strong>Stake: ${sym}${parseFloat(s.stake_amount).toFixed(2)}</strong>
                            <span class="text-muted"> | ${s.flip_count} flips | ${date}</span>
                        </div>
                        <span class="hi-status ${statusClass}">${statusText}</span>
                    </div>`;
                }).join('');
            }
        } catch (e) {
            container.innerHTML = '<p class="text-muted">Error loading history</p>';
        }
    }

    // ==================== MOMO ACCOUNT MANAGEMENT ====================

    async function loadMomoAccounts() {
        const listEl = document.getElementById('momo-accounts-list');
        const addBtn = document.getElementById('add-momo-btn');
        const limitText = document.getElementById('momo-limit-text');
        if (!listEl) return;

        try {
            const resp = await API.get('/payments/momo-accounts/');
            if (!resp.ok) { listEl.innerHTML = '<p class="text-muted">Could not load accounts</p>'; return; }
            const data = await resp.json();
            const accounts = data.accounts || [];

            if (accounts.length === 0) {
                listEl.innerHTML = '<p class="text-muted">No payment accounts yet. Add one to deposit or withdraw.</p>';
            } else {
                listEl.innerHTML = accounts.map(a => {
                    const nwClass = (a.network || '').toLowerCase();
                    const nwName = NETWORK_NAMES[a.network] || a.network;
                    const isPrimary = a.is_primary;
                    return `<div class="momo-account-card${isPrimary ? ' primary' : ''}">
                        <div class="momo-account-info">
                            <span class="momo-account-name">${a.verified_name}</span>
                            <span class="momo-account-number">${a.mobile_number} <span class="badge-network ${nwClass}">${nwName}</span></span>
                        </div>
                        <div class="momo-account-actions">
                            ${isPrimary ? '<span class="badge-primary">Primary</span>' : `<button class="btn-tiny" onclick="switchPrimaryMomo('${a.id}')">Set Primary</button><button class="btn-tiny danger" onclick="removeMomoAccount('${a.id}')">Remove</button>`}
                        </div>
                    </div>`;
                }).join('');
            }

            if (addBtn) addBtn.style.display = accounts.length >= 3 ? 'none' : 'block';
            if (limitText) limitText.textContent = `${accounts.length}/3 accounts`;
        } catch (e) {
            listEl.innerHTML = '<p class="text-muted">Error loading accounts</p>';
        }
    }

    // Expose to global scope for inline onclick handlers
    window.switchPrimaryMomo = async function(accountId) {
        try {
            const resp = await API.post('/payments/momo-accounts/set-primary/', { account_id: accountId });
            const data = await resp.json();
            if (data.success) {
                loadMomoAccounts();
            } else {
                alert(data.error || 'Failed to switch primary');
            }
        } catch (e) { alert('Network error'); }
    };

    window.removeMomoAccount = async function(accountId) {
        if (!confirm('Remove this payment account?')) return;
        try {
            const resp = await API.post('/payments/momo-accounts/remove/', { account_id: accountId });
            const data = await resp.json();
            if (data.success) {
                loadMomoAccounts();
            } else {
                alert(data.error || 'Failed to remove account');
            }
        } catch (e) { alert('Network error'); }
    };

    // Profile add-momo phone input handler
    let _profileVerifyTimeout = null;
    function handleProfileMomoPhoneInput() {
        const phone = document.getElementById('profile-momo-phone').value.replace(/\D/g, '');
        const networkEl = document.getElementById('profile-momo-network');
        const nw = detectNetworkFromPhone(phone);

        if (nw && phone.length >= 3) {
            networkEl.textContent = NETWORK_NAMES[nw] || nw;
            networkEl.className = 'network-badge ' + nw.toLowerCase();
            networkEl.style.display = 'inline-block';
        } else {
            networkEl.style.display = 'none';
        }

        const verifyStatus = document.getElementById('profile-momo-verify-status');
        const spinner = document.getElementById('profile-momo-spinner');
        const verifyText = document.getElementById('profile-momo-verify-text');

        if (_profileVerifyTimeout) clearTimeout(_profileVerifyTimeout);
        if (phone.length === 10 && nw) {
            _profileVerifyTimeout = setTimeout(async () => {
                verifyStatus.style.display = 'flex';
                spinner.style.display = 'inline-block';
                verifyText.textContent = 'Verifying...';

                try {
                    const resp = await API.post('/payments/momo-accounts/add/', { mobile_number: phone });
                    const data = await resp.json();
                    spinner.style.display = 'none';
                    if (data.success) {
                        verifyText.textContent = `Added: ${data.account.verified_name}`;
                        verifyStatus.className = 'verify-status';
                        document.getElementById('add-momo-form').style.display = 'none';
                        document.getElementById('add-momo-btn').style.display = 'block';
                        document.getElementById('profile-momo-phone').value = '';
                        loadMomoAccounts();
                    } else {
                        verifyText.textContent = data.error || 'Verification failed';
                        verifyStatus.className = 'verify-status error';
                    }
                } catch (e) {
                    spinner.style.display = 'none';
                    verifyText.textContent = 'Network error';
                    verifyStatus.className = 'verify-status error';
                }
            }, 400);
        } else {
            verifyStatus.style.display = 'none';
        }
    }

    async function loadReferral() {
        try {
            const resp = await API.get('/accounts/profile/');
            if (resp.ok) {
                const player = await resp.json();
                // referral code is generated at login, get it from profile
                const refLink = window.location.origin + '/?ref=' + (player.id || '').substring(0, 8);
                document.getElementById('referral-link').value = refLink;
            }
        } catch (e) { /* ignore */ }
    }

    // ==================== EVENT BINDINGS ====================
    function bindEvents() {
        // Start game
        document.getElementById('start-game-btn')?.addEventListener('click', startGame);

        // Quick stakes
        document.querySelectorAll('.quick-stake').forEach(btn => {
            btn.addEventListener('click', () => {
                document.getElementById('stake-input').value = btn.dataset.amount;
            });
        });

        // Game buttons
        document.getElementById('flip-btn')?.addEventListener('click', doFlip);
        document.getElementById('cashout-btn')?.addEventListener('click', doCashout);
        document.getElementById('pause-btn')?.addEventListener('click', doPause);
        document.getElementById('confirm-pause-btn')?.addEventListener('click', confirmPause);
        document.getElementById('game-back-btn')?.addEventListener('click', returnToLobby);

        // Loss/Cashout overlays
        document.getElementById('play-again-btn')?.addEventListener('click', () => {
            document.getElementById('loss-overlay').classList.add('hidden');
            returnToLobby();
        });
        document.getElementById('loss-lobby-btn')?.addEventListener('click', () => {
            document.getElementById('loss-overlay').classList.add('hidden');
            returnToLobby();
        });
        document.getElementById('cashout-lobby-btn')?.addEventListener('click', () => {
            document.getElementById('cashout-overlay').classList.add('hidden');
            returnToLobby();
        });

        // Lobby actions
        document.getElementById('deposit-btn')?.addEventListener('click', () => showModal('deposit-modal'));
        document.getElementById('withdraw-btn')?.addEventListener('click', () => showModal('withdraw-modal'));
        document.getElementById('history-btn')?.addEventListener('click', () => {
            showModal('history-modal');
            loadHistory();
        });
        document.getElementById('referral-btn')?.addEventListener('click', () => {
            showModal('referral-modal');
            loadReferral();
        });

        // Profile panel — load momo accounts on open
        document.getElementById('profile-btn')?.addEventListener('click', () => {
            document.getElementById('profile-panel')?.classList.add('show');
            document.getElementById('profile-panel')?.classList.remove('hidden');
            loadMomoAccounts();
        });
        document.getElementById('game-profile-btn')?.addEventListener('click', () => {
            document.getElementById('profile-panel')?.classList.add('show');
            document.getElementById('profile-panel')?.classList.remove('hidden');
            loadMomoAccounts();
        });

        // Momo account management in profile
        document.getElementById('add-momo-btn')?.addEventListener('click', () => {
            document.getElementById('add-momo-form').style.display = 'block';
            document.getElementById('add-momo-btn').style.display = 'none';
            document.getElementById('profile-momo-phone').value = '';
            document.getElementById('profile-momo-verify-status').style.display = 'none';
            document.getElementById('profile-momo-phone').focus();
        });
        document.getElementById('cancel-add-momo')?.addEventListener('click', () => {
            document.getElementById('add-momo-form').style.display = 'none';
            document.getElementById('add-momo-btn').style.display = 'block';
        });
        document.getElementById('profile-momo-phone')?.addEventListener('input', handleProfileMomoPhoneInput);
        document.getElementById('close-profile')?.addEventListener('click', () => {
            document.getElementById('profile-panel')?.classList.remove('show');
        });

        // Profile menu items
        document.getElementById('menu-history')?.addEventListener('click', () => {
            document.getElementById('profile-panel')?.classList.remove('show');
            showModal('history-modal');
            loadHistory();
        });
        document.getElementById('menu-referral')?.addEventListener('click', () => {
            document.getElementById('profile-panel')?.classList.remove('show');
            showModal('referral-modal');
            loadReferral();
        });
        document.getElementById('menu-logout')?.addEventListener('click', () => {
            document.getElementById('profile-panel')?.classList.remove('show');
            logout();
        });

        // Modal close buttons
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', () => hideModal(btn.dataset.modal));
        });
        document.querySelectorAll('.modal-backdrop').forEach(bd => {
            bd.addEventListener('click', () => {
                bd.parentElement?.classList.add('hidden');
            });
        });

        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const tabId = btn.dataset.tab;
                btn.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                btn.closest('.modal-body').querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
                document.getElementById(tabId)?.classList.add('active');
            });
        });

        // Phone input: auto-detect network + verify name
        document.getElementById('dep-phone')?.addEventListener('input', handleDepPhoneInput);
        document.getElementById('wdr-phone')?.addEventListener('input', handleWdrPhoneInput);

        // Payment buttons
        document.getElementById('dep-momo-btn')?.addEventListener('click', depositMoMo);
        document.getElementById('dep-card-btn')?.addEventListener('click', depositCard);
        document.getElementById('wdr-btn')?.addEventListener('click', doWithdraw);

        // Copy referral
        document.getElementById('copy-referral')?.addEventListener('click', () => {
            const input = document.getElementById('referral-link');
            if (input) {
                navigator.clipboard?.writeText(input.value);
                showToast('Link copied!');
            }
        });

        // Share WhatsApp
        document.getElementById('share-whatsapp')?.addEventListener('click', () => {
            const link = document.getElementById('referral-link')?.value;
            if (link) {
                window.open(`https://wa.me/?text=${encodeURIComponent('Play Cashflip and win big! 🎰💵 ' + link)}`, '_blank');
            }
        });

        // Keyboard shortcut for flip
        document.addEventListener('keydown', (e) => {
            if (e.code === 'Space' && document.getElementById('game-screen')?.classList.contains('active')) {
                e.preventDefault();
                doFlip();
            }
        });
    }

    // ==================== INIT ====================
    async function init() {
        bindEvents();
        initAuth();

        // Loading screen
        setTimeout(() => {
            if (state.token) {
                // Schedule proactive refresh for returning user
                scheduleTokenRefresh();
                // Try to resume session
                enterLobby();
            } else {
                showScreen('auth-screen');
            }
        }, 1800);
    }

    // Start
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
