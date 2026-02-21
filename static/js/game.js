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
        gameConfig: null,
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
    let scene, camera, renderer, particles;
    let animationId;
    let _sceneTime = 0;
    let _bgOrbs = [];

    function initScene() {
        const canvas = document.getElementById('game-canvas');
        if (!canvas) return;

        scene = new THREE.Scene();
        scene.background = new THREE.Color(0x060a14);
        scene.fog = new THREE.FogExp2(0x060a14, 0.012);

        camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 120);
        camera.position.set(0, 0.5, 6);

        renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.1;

        // === Premium Lighting ===
        const ambientLight = new THREE.AmbientLight(0x1a1a3a, 0.4);
        scene.add(ambientLight);

        // Warm overhead spotlight — pool-of-light on the note area
        const mainSpot = new THREE.SpotLight(0xffd700, 2.5, 25, Math.PI / 5, 0.6, 1.5);
        mainSpot.position.set(0, 8, 4);
        mainSpot.target.position.set(0, 0, 0);
        scene.add(mainSpot);
        scene.add(mainSpot.target);

        // Teal rim lights flanking the table
        const rimLeft = new THREE.PointLight(0x00bfa6, 0.8, 18);
        rimLeft.position.set(-6, 3, 2);
        scene.add(rimLeft);

        const rimRight = new THREE.PointLight(0x00bfa6, 0.8, 18);
        rimRight.position.set(6, 3, 2);
        scene.add(rimRight);

        // Purple underglow
        const underGlow = new THREE.PointLight(0x8b5cf6, 0.35, 12);
        underGlow.position.set(0, -3, 2);
        scene.add(underGlow);

        // Warm fill from behind camera
        const fillLight = new THREE.PointLight(0xffeedd, 0.25, 20);
        fillLight.position.set(0, 2, 8);
        scene.add(fillLight);

        // === Glossy Casino Table ===
        const tableGeo = new THREE.PlaneGeometry(22, 14, 1, 1);
        const tableMat = new THREE.MeshStandardMaterial({
            color: 0x0a3d22,
            roughness: 0.25,
            metalness: 0.5,
            envMapIntensity: 0.6,
        });
        const table = new THREE.Mesh(tableGeo, tableMat);
        table.rotation.x = -Math.PI / 2;
        table.position.y = -2.5;
        scene.add(table);

        // Gold trim ring around the table
        const ringGeo = new THREE.RingGeometry(7.5, 7.8, 64);
        const ringMat = new THREE.MeshStandardMaterial({
            color: 0xd4a72c, roughness: 0.2, metalness: 0.9,
            emissive: 0xd4a72c, emissiveIntensity: 0.15,
        });
        const ring = new THREE.Mesh(ringGeo, ringMat);
        ring.rotation.x = -Math.PI / 2;
        ring.position.y = -2.48;
        scene.add(ring);

        // === Background Orbs (slow-moving ambient glow) ===
        _bgOrbs = [];
        const orbData = [
            { color: 0x00bfa6, x: -4, y: 1, z: -6, size: 3.5 },
            { color: 0xffd700, x: 5, y: 2, z: -8, size: 2.8 },
            { color: 0x8b5cf6, x: 0, y: -1, z: -10, size: 4.0 },
        ];
        orbData.forEach((o, i) => {
            const geo = new THREE.SphereGeometry(o.size, 16, 16);
            const mat = new THREE.MeshBasicMaterial({
                color: o.color, transparent: true, opacity: 0.035,
            });
            const mesh = new THREE.Mesh(geo, mat);
            mesh.position.set(o.x, o.y, o.z);
            scene.add(mesh);
            _bgOrbs.push({ mesh, baseX: o.x, baseY: o.y, speed: 0.15 + i * 0.08 });
        });

        // === Enhanced Particle System ===
        const particleGeo = new THREE.BufferGeometry();
        const particleCount = 500;
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);
        const sizes = new Float32Array(particleCount);

        for (let i = 0; i < particleCount; i++) {
            positions[i * 3] = (Math.random() - 0.5) * 24;
            positions[i * 3 + 1] = (Math.random() - 0.5) * 12;
            positions[i * 3 + 2] = (Math.random() - 0.5) * 14;
            // Gold/teal color mix
            const hue = Math.random() < 0.6 ? (0.12 + Math.random() * 0.08) : (0.46 + Math.random() * 0.04);
            const c = new THREE.Color().setHSL(hue, 0.9, 0.65);
            colors[i * 3] = c.r;
            colors[i * 3 + 1] = c.g;
            colors[i * 3 + 2] = c.b;
            sizes[i] = 0.03 + Math.random() * 0.09;
        }

        particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        particleGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

        const particleMat = new THREE.PointsMaterial({
            size: 0.06,
            vertexColors: true,
            transparent: true,
            opacity: 0.7,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
            sizeAttenuation: true,
        });
        particles = new THREE.Points(particleGeo, particleMat);
        scene.add(particles);

        // === Animate ===
        const _baseCamY = camera.position.y;
        function animate() {
            animationId = requestAnimationFrame(animate);
            _sceneTime += 0.008;

            // Particle drift + gentle upward float
            particles.rotation.y += 0.0004;
            const posArr = particles.geometry.attributes.position.array;
            for (let i = 0; i < particleCount; i++) {
                posArr[i * 3 + 1] += 0.002 + Math.sin(_sceneTime * 2 + i) * 0.001;
                if (posArr[i * 3 + 1] > 6) posArr[i * 3 + 1] = -6;
            }
            particles.geometry.attributes.position.needsUpdate = true;

            // Background orb drift
            _bgOrbs.forEach((o) => {
                o.mesh.position.x = o.baseX + Math.sin(_sceneTime * o.speed) * 1.5;
                o.mesh.position.y = o.baseY + Math.cos(_sceneTime * o.speed * 0.7) * 0.8;
            });

            // Subtle camera breathing
            camera.position.y = _baseCamY + Math.sin(_sceneTime * 0.5) * 0.04;

            renderer.render(scene, camera);
        }
        animate();

        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
    }

    // ==================== ASSET URL HELPER ====================
    // Uploaded files return full URLs (/media/... or https://cdn...),
    // static paths need /static/ prefix.
    // For Cloudinary URLs, inject c_fill,ar_16:9,g_center to ensure
    // images fill the 16:9 card area without black bars.
    function _assetUrl(path) {
        if (!path) return '';
        if (path.startsWith('/') || path.startsWith('http')) return path;
        return `/static/${path}`;
    }

    function _cloudinaryFill(url) {
        if (!url) return url;
        // Never transform animated GIFs — Cloudinary c_fill breaks animation
        if (url.match(/\.(gif)(\?|$)/i)) return url;
        const marker = '/image/upload/';
        const idx = url.indexOf(marker);
        if (idx === -1) return url;
        const before = url.substring(0, idx + marker.length);
        const after = url.substring(idx + marker.length);
        if (after.startsWith('c_') || after.startsWith('w_') || after.startsWith('ar_')) return url;
        return before + 'c_fill,ar_16:9,g_center/' + after;
    }

    function _gifStaticFrame(url) {
        if (!url) return url;
        const marker = '/image/upload/';
        const idx = url.indexOf(marker);
        if (idx === -1) return url;
        const before = url.substring(0, idx + marker.length);
        const after = url.substring(idx + marker.length);
        if (after.startsWith('c_') || after.startsWith('pg_')) return url;
        return before + 'c_fill,ar_16:9,g_center,pg_1/' + after;
    }

    // Cloudinary transform for animated GIFs:
    // dl_X controls frame delay (centiseconds), e_trim removes transparent borders,
    // c_pad adds dark bg to reach 16:9.
    // durationMs = desired total animation time, frames = number of GIF frames.
    function _gifAnimatedFill(url, durationMs, frames) {
        if (!url) return url;
        const marker = '/image/upload/';
        const idx = url.indexOf(marker);
        if (idx === -1) return url;
        const before = url.substring(0, idx + marker.length);
        const after = url.substring(idx + marker.length);
        if (after.startsWith('c_') || after.startsWith('e_') || after.startsWith('dl_')) return url;
        // Compute frame delay: dl_X where X is centiseconds (1/100 sec)
        const numFrames = frames || 31;
        const delayMs = (durationMs || 1500) / numFrames;
        const dlVal = Math.max(2, Math.round(delayMs / 10)); // minimum 20ms per frame
        return before + `dl_${dlVal}/c_pad,ar_16:9,g_center,b_rgb:0d0d1a/` + after;
    }

    // ==================== STAKE TIER DENOMINATION FILTER ====================
    function _getDenomsForStake(stakeAmount) {
        const allDenoms = state.denominations || [];
        const nonZero = allDenoms.filter(d => !d.is_zero);
        const tiers = state.gameConfig?.stake_tiers || [];
        if (tiers.length === 0 || !stakeAmount) return nonZero;
        const stake = parseFloat(stakeAmount);
        const tier = tiers.find(t => t.is_active && stake >= parseFloat(t.min_stake) && stake <= parseFloat(t.max_stake));
        if (!tier || !tier.denomination_ids || tier.denomination_ids.length === 0) return nonZero;
        const tierDenoms = nonZero.filter(d => tier.denomination_ids.includes(d.id));
        return tierDenoms.length > 0 ? tierDenoms : nonZero;
    }

    // ==================== GIF / FACE / VIDEO PRELOAD CACHE ====================
    const _gifFrameCache = {};
    const _preloadedImages = {};
    const _preloadedVideos = {}; // { url: HTMLVideoElement } — pre-buffered videos

    function _preloadGifFirstFrames() {
        const denoms = state.denominations || [];
        denoms.forEach(d => {
            if (d.face_image_path && !d.is_zero) {
                const faceUrl = _cloudinaryFill(_assetUrl(d.face_image_path));
                if (!_preloadedImages[faceUrl]) {
                    const img = new Image();
                    img.crossOrigin = 'anonymous';
                    img.src = faceUrl;
                    _preloadedImages[faceUrl] = img;
                }
            }
            if (d.flip_gif_path && !d.is_zero) {
                // Preload static first frame (for card face display)
                const staticUrl = _gifStaticFrame(_assetUrl(d.flip_gif_path));
                if (!_preloadedImages[staticUrl]) {
                    const sImg = new Image();
                    sImg.crossOrigin = 'anonymous';
                    sImg.src = staticUrl;
                    _preloadedImages[staticUrl] = sImg;
                }
                // Preload animated GIF with fill + speed transform (for flip animation)
                const animSpeed = state.gameConfig?.flip_animation_speed_ms || 1500;
                const animFrames = d.flip_sequence_frames || 31;
                const animUrl = _gifAnimatedFill(_assetUrl(d.flip_gif_path), animSpeed, animFrames);
                if (!_preloadedImages[animUrl]) {
                    const aImg = new Image();
                    aImg.crossOrigin = 'anonymous';
                    aImg.src = animUrl;
                    _preloadedImages[animUrl] = aImg;
                }
            }
        });
        // Preload denomination flip videos (video mode)
        _preloadDenomVideos();
    }

    function _preloadDenomVideos() {
        const denoms = state.denominations || [];
        denoms.forEach(d => {
            if (d.flip_video_path && !d.is_zero) {
                const url = _assetUrl(d.flip_video_path);
                if (!_preloadedVideos[url]) {
                    const v = document.createElement('video');
                    v.muted = true;
                    v.playsInline = true;
                    v.preload = 'auto';
                    v.src = url;
                    v.load(); // start buffering
                    _preloadedVideos[url] = v;
                }
            }
        });
    }

    function _isVideoMode() {
        return (state.gameConfig?.flip_animation_mode || 'gif') === 'video';
    }

    // Shared style for video-as-card elements (looks identical to an image)
    const _videoCardStyle = 'width:100%;height:100%;object-fit:cover;display:block;' +
        'border-radius:inherit;pointer-events:none;background:#000;';

    // ==================== STACKED BUNDLE NOTE FLIPPER + SWIPE ====================
    let _noteFlipCount = 0;
    let _swipeStartY = 0;
    let _swipeStartX = 0;
    let _swipeDragging = false;
    let _swipeCurrentAngle = 0;
    const SWIPE_THRESHOLD = 50; // px needed to commit the flip
    let _autoFlipTimer = null;
    let _autoFlipCountdown = 0;
    let _autoFlipTick = null;
    let _isFirstCard = true; // Only show start_flip_image on the very first card

    function initNoteStage() {
        _noteFlipCount = 0;
        _isFirstCard = true;
        const stage = document.getElementById('note-stage');
        if (stage) stage.innerHTML = '';
        const pile = document.getElementById('note-pile');
        if (pile) pile.classList.remove('visible');
        const pileCount = document.getElementById('pile-count');
        if (pileCount) pileCount.textContent = '0';
        const total = document.getElementById('note-running-total');
        if (total) total.classList.remove('visible');
        const nrtVal = document.getElementById('nrt-value');
        if (nrtVal) nrtVal.textContent = `${state.session?.currency?.symbol || 'GH₵'}0.00`;
        _buildStack();
        _placeReadyCard();
        _bindSwipeEvents();
        _showTutorialIfNeeded();
    }

    function _buildStack() {
        const stage = document.getElementById('note-stage');
        if (!stage) return;
        // Remove old stack
        const old = stage.querySelector('.note-stack');
        if (old) old.remove();
        // Build stack layers (visual depth of the bundle)
        const stack = document.createElement('div');
        stack.className = 'note-stack';
        for (let i = 0; i < 4; i++) {
            const layer = document.createElement('div');
            layer.className = 'note-stack-layer';
            stack.appendChild(layer);
        }
        stage.appendChild(stack);
    }

    function _isGifMode() {
        const mode = state.gameConfig?.flip_animation_mode || 'gif';
        return mode === 'gif';
    }

    const _imgStyle = 'position:absolute;inset:0;width:100%;height:100%;object-fit:cover;border-radius:inherit;display:block;';

    // Start flip image — shown only on the very first card of a new session.
    function _startFlipCardHTML() {
        const startUrl = state.gameConfig?.start_flip_image_url;
        if (startUrl) {
            return `<img src="${startUrl}" alt="card" style="${_imgStyle}" />`;
        }
        return ''; // Empty — dark card background shows through
    }

    // Random denomination glimpse — shows a denomination's static first frame.
    // Used for all cards AFTER the first flip (next-card-underneath).
    function _randomDenomCardHTML() {
        const denoms = state.session?.currency?.denominations || state.denominations || [];
        const nonZero = denoms.filter(d => !d.is_zero);
        if (nonZero.length > 0) {
            const denom = nonZero[Math.floor(Math.random() * nonZero.length)];
            const imgUrl = _getCardImageUrl(denom);
            if (imgUrl) {
                return `<img src="${imgUrl}" alt="card" style="${_imgStyle}" />`;
            }
        }
        // Fallback SVG
        const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='400' height='225' viewBox='0 0 400 225'>`
            + `<rect width='400' height='225' fill='%230d0d2b'/>`
            + `<text x='200' y='105' text-anchor='middle' font-size='36' font-weight='800' fill='%23ffd700'>FLIP</text>`
            + `<text x='200' y='135' text-anchor='middle' font-size='12' fill='rgba(255,255,255,0.5)' letter-spacing='2'>TAP TO REVEAL</text>`
            + `</svg>`;
        return `<img src="data:image/svg+xml,${svg}" alt="card" style="${_imgStyle}" />`;
    }

    function _getCardImageUrl(denom) {
        // GIF mode: the GIF's first frame IS the card face (no separate face image)
        if (_isGifMode() && denom?.flip_gif_path) {
            return _gifStaticFrame(_assetUrl(denom.flip_gif_path));
        }
        // Legacy/other modes: use face image
        const displayMode = state.gameConfig?.flip_display_mode || 'face_then_gif';
        if (displayMode === 'gif_only' && denom?.flip_gif_path) {
            return _gifStaticFrame(_assetUrl(denom.flip_gif_path));
        }
        if (denom?.face_image_path) {
            return _cloudinaryFill(_assetUrl(denom.face_image_path));
        }
        return denom?.front_image_url || denom?.back_image_url || null;
    }

    function _placeReadyCard() {
        const stage = document.getElementById('note-stage');
        if (!stage) return;
        // Remove any previous active note (safety)
        const prev = document.getElementById('active-note');
        if (prev) prev.remove();
        // Also remove any lingering next-note
        const prevNext = document.getElementById('next-note');
        if (prevNext) prevNext.remove();

        const card = document.createElement('div');
        card.className = 'banknote-card entering';
        card.id = 'active-note';
        card.style.zIndex = '1';

        // First card of session: configurable start flip image.
        // All subsequent cards: empty dark card — denomination appears on flip.
        if (_isFirstCard) {
            card.innerHTML = _startFlipCardHTML();
            _isFirstCard = false;
        }
        // else: empty — .banknote-card CSS gives dark background

        stage.appendChild(card);
        _startAutoFlipTimer();
    }

    // ---- SWIPE GESTURE ENGINE (both vertical & horizontal) ----
    let _swipeBound = false;
    function _bindSwipeEvents() {
        if (_swipeBound) return;
        _swipeBound = true;
        const zone = document.getElementById('note-flipper');
        if (!zone) return;

        zone.addEventListener('touchstart', _onSwipeStart, { passive: true });
        zone.addEventListener('touchmove', _onSwipeMove, { passive: false });
        zone.addEventListener('touchend', _onSwipeEnd, { passive: true });
        zone.addEventListener('touchcancel', _onSwipeEnd, { passive: true });

        zone.addEventListener('mousedown', _onSwipeStart);
        zone.addEventListener('mousemove', _onSwipeMove);
        zone.addEventListener('mouseup', _onSwipeEnd);
        zone.addEventListener('mouseleave', _onSwipeEnd);
    }

    function _getXY(e) {
        const t = e.touches ? e.touches[0] : e;
        return { x: t.clientX, y: t.clientY };
    }

    function _onSwipeStart(e) {
        if (state.isFlipping || !state.session || state.session.status !== 'active') return;
        const tut = document.getElementById('swipe-tutorial');
        if (tut && !tut.classList.contains('hidden')) {
            tut.classList.add('hidden');
            localStorage.setItem('cf_tut_seen', '1');
        }
        const p = _getXY(e);
        _swipeStartX = p.x;
        _swipeStartY = p.y;
        _swipeDragging = true;
        _swipeCurrentAngle = 0;
    }

    function _onSwipeMove(e) {
        if (!_swipeDragging) return;
        const p = _getXY(e);
        const dx = _swipeStartX - p.x; // positive = swiped left
        if (dx <= 0) { _swipeCurrentAngle = 0; return; }
        if (e.cancelable) e.preventDefault();
        const ratio = Math.min(dx / 200, 1);
        _swipeCurrentAngle = ratio * ratio * 90;
        if (dx >= SWIPE_THRESHOLD && dx < SWIPE_THRESHOLD + 12) {
            _hapticTick();
        }
    }

    function _onSwipeEnd() {
        if (!_swipeDragging) return;
        _swipeDragging = false;
        if (_swipeCurrentAngle >= 35) {
            _stopAutoFlipTimer();
            _hapticHeavy();
            doFlip();
        }
        _swipeCurrentAngle = 0;
    }

    // ---- HAPTIC FEEDBACK ----
    function _hapticTick() {
        if (navigator.vibrate) navigator.vibrate(10);
    }
    function _hapticHeavy() {
        if (navigator.vibrate) navigator.vibrate([15, 30, 15]);
    }

    // ---- AUTO-FLIP COUNTDOWN TIMER ----
    function _startAutoFlipTimer() {
        _stopAutoFlipTimer();
        const seconds = state.gameConfig?.auto_flip_seconds || 8;
        if (seconds <= 0) return;
        _autoFlipCountdown = seconds;
        const circumference = 339.292;
        const ring = document.getElementById('autoflip-ring');
        const progress = document.getElementById('afr-progress');
        const text = document.getElementById('afr-text');
        if (!ring || !progress || !text) return;

        ring.classList.add('visible');
        text.textContent = seconds;
        progress.style.strokeDashoffset = '0';
        progress.classList.remove('urgent');

        _autoFlipTick = setInterval(() => {
            _autoFlipCountdown--;
            if (_autoFlipCountdown <= 0) {
                _stopAutoFlipTimer();
                if (!state.isFlipping && state.session?.status === 'active') {
                    _hapticHeavy();
                    const card = document.getElementById('active-note');
                    if (card) {
                        card.classList.remove('entering', 'spring-back', 'dragging');
                        card.style.transform = '';
                    }
                    doFlip();
                }
                return;
            }
            text.textContent = _autoFlipCountdown;
            const fraction = 1 - (_autoFlipCountdown / seconds);
            progress.style.strokeDashoffset = (fraction * circumference).toFixed(1);
            if (_autoFlipCountdown <= 3) progress.classList.add('urgent');
        }, 1000);
    }

    function _stopAutoFlipTimer() {
        if (_autoFlipTick) { clearInterval(_autoFlipTick); _autoFlipTick = null; }
        const ring = document.getElementById('autoflip-ring');
        if (ring) ring.classList.remove('visible');
    }

    // ---- TUTORIAL OVERLAY ----
    function _showTutorialIfNeeded() {
        if (localStorage.getItem('cf_tut_seen')) return;
        const tut = document.getElementById('swipe-tutorial');
        if (!tut) return;
        tut.classList.remove('hidden');
        tut.addEventListener('click', () => {
            tut.classList.add('hidden');
            localStorage.setItem('cf_tut_seen', '1');
        }, { once: true });
        setTimeout(() => {
            if (!tut.classList.contains('hidden')) {
                tut.classList.add('hidden');
                localStorage.setItem('cf_tut_seen', '1');
            }
        }, 5000);
    }

    // ---- FLIP SOUND ----
    let _flipSound = null;
    let _flipSoundUrl = null; // tracks which URL is loaded
    function _playFlipSound() {
        if (!state.gameConfig?.flip_sound_enabled) return;
        try {
            // Use custom sound URL from admin config, fallback to default
            const customUrl = state.gameConfig?.flip_sound_url;
            const soundUrl = customUrl || '/static/sounds/money-flip.mp3';

            // Reload audio if URL changed (admin uploaded a new sound)
            if (!_flipSound || _flipSoundUrl !== soundUrl) {
                _flipSound = new Audio(soundUrl);
                _flipSound.volume = 0.7;
                _flipSoundUrl = soundUrl;
                // Fallback: if custom URL fails, use default
                if (customUrl) {
                    _flipSound.onerror = () => {
                        _flipSound = new Audio('/static/sounds/money-flip.mp3');
                        _flipSound.volume = 0.7;
                        _flipSoundUrl = '/static/sounds/money-flip.mp3';
                        _flipSound.play().catch(() => {});
                    };
                }
            }
            _flipSound.currentTime = 0;
            _flipSound.play().catch(() => {});
        } catch (e) {}
    }

    // ---- FLIP NOTE ANIMATION (called after API returns) ----
    function flipNoteAnimation(isZero, value, denomData) {
        return new Promise((resolve) => {
            state.isFlipping = true;
            const sym = state.session?.currency?.symbol || 'GH₵';
            const card = document.getElementById('active-note');
            if (!card) { state.isFlipping = false; resolve(); return; }

            // Get animation config from game config
            const animMode = state.gameConfig?.flip_animation_mode || 'gif';
            const animSpeed = state.gameConfig?.flip_animation_speed_ms || 1500;

            // Play flip sound
            _playFlipSound();

            // ZERO denomination: show 0f.jpg face image, no animation needed.
            // The zero popup (zero-note overlay) handles the result display.
            if (isZero) {
                card.classList.remove('entering', 'dragging', 'spring-back');
                card.style.transform = '';
                card.style.opacity = '1';
                const zeroFace = denomData?.face_image_path
                    ? _cloudinaryFill(_assetUrl(denomData.face_image_path)) : '/static/images/Cedi-Face/0f.jpg';
                const img = card.querySelector('img');
                if (img) {
                    img.src = zeroFace;
                } else {
                    card.innerHTML = `<img src="${zeroFace}" alt="zero" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;border-radius:10px;display:block;" />`;
                }
                _noteFlipCount++;
                state.isFlipping = false;
                resolve();
                return;
            }

            // Non-zero: choose animation mode
            const gifPath = denomData?.flip_gif_path;
            const seqPrefix = denomData?.flip_sequence_prefix;
            const videoPath = denomData?.flip_video_path;

            // Prefer video if configured
            if (animMode === 'video' && videoPath) {
                _flipWithVideo(card, videoPath, animSpeed, value, sym, resolve, denomData);
                return;
            } else if (videoPath && !gifPath && !seqPrefix) {
                // Auto-fallback to video if it's the only asset
                _flipWithVideo(card, videoPath, animSpeed, value, sym, resolve, denomData);
                return;
            } else if (animMode === 'gif' && gifPath) {
                _flipWithGif(card, gifPath, animSpeed, value, sym, resolve, denomData);
                return;
            } else if (animMode === 'png' && seqPrefix) {
                const seqFrames = denomData?.flip_sequence_frames || 31;
                _flipWithSequence(card, seqPrefix, seqFrames, animSpeed, value, sym, resolve);
                return;
            } else if (gifPath) {
                _flipWithGif(card, gifPath, animSpeed, value, sym, resolve, denomData);
                return;
            } else if (seqPrefix) {
                const seqFrames = denomData?.flip_sequence_frames || 31;
                _flipWithSequence(card, seqPrefix, seqFrames, animSpeed, value, sym, resolve);
                return;
            }

            // --- FALLBACK: CSS-based animation (no assets available) ---
            _flipWithCSS(card, isZero, value, sym, denomData, resolve);
        });
    }

    // ---- GIF FLIP ANIMATION ----
    // Card starts empty (dark). On flip: load the denomination's animated GIF
    // directly — the GIF IS the flip animation revealing the denomination (WYSIWYG).
    // Uses raw GIF URL (no Cloudinary speed transforms — they break animation).
    // Cache-bust forces GIF to restart from frame 0 every time.
    function _flipWithGif(card, gifPath, durationMs, value, sym, resolve, denomData) {
        const gifUrl = _assetUrl(gifPath);
        const cacheBust = `?cb=${Date.now()}`;
        let _gifFired = false; // Double-fire guard

        card.classList.remove('entering', 'dragging', 'spring-back');
        card.style.transform = '';
        card.style.opacity = '1';

        // Pre-place next card underneath (hidden, empty dark card)
        _placeNextCardUnderneath();

        // Load the denomination's flip GIF directly onto the card.
        // The GIF animation reveals the denomination — WYSIWYG.
        card.innerHTML = `<img src="${gifUrl}${cacheBust}" alt="flip" style="${_imgStyle}" />`;

        // Guarded completion handler — only fires once
        const onGifEnd = () => {
            if (_gifFired) return;
            _gifFired = true;

            // Swap to denomination face image as final resting state (clear WYSIWYG visual)
            const faceUrl = denomData?.face_image_path
                ? _cloudinaryFill(_assetUrl(denomData.face_image_path)) : null;
            if (faceUrl) {
                const img = card.querySelector('img');
                if (img) { img.src = faceUrl; img.style.cssText = _imgStyle; }
            }

            _noteFlipCount++;
            updateRunningTotal();
            const pile = document.getElementById('note-pile');
            const pileCount = document.getElementById('pile-count');
            if (pile) pile.classList.add('visible');
            if (pileCount) pileCount.textContent = _noteFlipCount;

            // Brief pause to show the denomination face, then move to pile
            setTimeout(() => {
                // Reveal the next card underneath (empty dark card)
                const nextCard = document.getElementById('next-note');
                if (nextCard) nextCard.style.opacity = '1';

                card.removeAttribute('id');
                card.classList.add('to-pile');
                card.addEventListener('animationend', () => card.remove(), { once: true });
                setTimeout(() => { if (card.parentNode) card.remove(); }, 600);

                // Promote the underneath card to active
                const next = document.getElementById('next-note');
                if (next) { next.id = 'active-note'; }
                _startAutoFlipTimer();
                state.isFlipping = false;
                resolve();
            }, 400); // 400ms pause to see the denomination face
        };

        // GIF plays for the configured duration, then show face + move to pile
        setTimeout(onGifEnd, durationMs);
    }

    // ---- MP4/WebM VIDEO FLIP ANIMATION ----
    // The card already contains a <video> paused at frame 0 (looks like a static image).
    // On flip: swap src to the correct denomination video, play naturally.
    // Pre-loaded videos ensure instant swap with no flash/loading.
    function _flipWithVideo(card, videoPath, durationMs, value, sym, resolve, denomData) {
        const videoUrl = _assetUrl(videoPath);
        let _videoFired = false; // Double-fire guard

        card.classList.remove('entering');

        // Pre-place next card underneath (hidden — also a paused video in video mode)
        _placeNextCardUnderneath();

        // Get existing video element from card (created by _placeReadyCard or _placeNextCardUnderneath)
        let video = card.querySelector('video');

        // If card doesn't have a video element yet (e.g. CSS fallback card), create one
        if (!video) {
            card.innerHTML = `<video muted playsinline preload="auto"
                style="${_videoCardStyle}" src="${videoUrl}"></video>`;
            video = card.querySelector('video');
        } else {
            // Swap src to the correct denomination's flip video (if different)
            const currentSrc = video.src || '';
            if (!currentSrc.endsWith(videoPath) && !currentSrc.includes(videoPath)) {
                video.src = videoUrl;
                video.load();
            }
        }

        // Guarded completion handler — only fires once
        const onVideoEnd = () => {
            if (_videoFired) return;
            _videoFired = true;

            _noteFlipCount++;
            updateRunningTotal();
            const pile = document.getElementById('note-pile');
            const pileCount = document.getElementById('pile-count');
            if (pile) pile.classList.add('visible');
            if (pileCount) pileCount.textContent = _noteFlipCount;

            // Reveal the next card underneath (also a paused video — looks like a static card)
            const nextCard = document.getElementById('next-note');
            if (nextCard) nextCard.style.opacity = '1';

            card.removeAttribute('id');
            card.classList.add('to-pile');
            card.addEventListener('animationend', () => card.remove(), { once: true });
            setTimeout(() => { if (card.parentNode) card.remove(); }, 600);

            // Promote next card to active
            const next = document.getElementById('next-note');
            if (next) {
                next.id = 'active-note';
                // Ensure the next card's video stays paused at frame 0
                const nextVid = next.querySelector('video');
                if (nextVid) { nextVid.pause(); nextVid.currentTime = 0; }
            }
            _startAutoFlipTimer();
            state.isFlipping = false;
            resolve();
        };

        // Fallback: if video completely fails, fall back to GIF or CSS
        const onVideoError = () => {
            if (_videoFired) return;
            _videoFired = true;
            const gifPath = denomData?.flip_gif_path;
            if (gifPath) {
                _flipWithGif(card, gifPath, durationMs, value, sym, resolve, denomData);
            } else {
                _flipWithCSS(card, false, value, sym, denomData, resolve);
            }
        };

        if (video) {
            video.addEventListener('ended', onVideoEnd, { once: true });
            video.addEventListener('error', onVideoError, { once: true });

            // Adjust playback rate so video duration matches admin-configured flip speed
            const applyPlaybackRate = () => {
                if (video.duration && video.duration > 0 && durationMs > 0) {
                    const desiredSec = durationMs / 1000;
                    const rate = video.duration / desiredSec;
                    video.playbackRate = Math.max(0.25, Math.min(4.0, rate));
                }
            };

            // Play from frame 0 once ready
            const tryPlay = () => {
                video.currentTime = 0;
                applyPlaybackRate();
                video.play().catch(() => {
                    // Autoplay blocked or decode error — timeout fallback
                    setTimeout(onVideoEnd, durationMs);
                });
            };

            // If metadata already loaded (preloaded), apply rate and play immediately
            if (video.readyState >= 2) {
                tryPlay();
            } else {
                video.addEventListener('loadedmetadata', () => tryPlay(), { once: true });
            }

            // Safety timeout: absolute maximum wait to prevent hang
            setTimeout(() => {
                if (!_videoFired) onVideoEnd();
            }, durationMs + 2000);
        } else {
            setTimeout(onVideoEnd, durationMs);
        }
    }

    // Place a new card underneath the current active card
    function _placeNextCardUnderneath() {
        const stage = document.getElementById('note-stage');
        if (!stage) return;
        // Don't duplicate
        if (document.getElementById('next-note')) return;

        const nextCard = document.createElement('div');
        nextCard.className = 'banknote-card';
        nextCard.id = 'next-note';
        nextCard.style.zIndex = '0';
        nextCard.style.opacity = '0'; // Hidden until current card exits
        // Empty card — dark background from .banknote-card CSS.
        // Denomination appears on flip via API result.

        // Insert underneath (before active card)
        const active = document.getElementById('active-note');
        if (active) {
            stage.insertBefore(nextCard, active);
        } else {
            stage.appendChild(nextCard);
        }
    }

    // ---- PNG SEQUENCE FLIP ANIMATION ----
    function _flipWithSequence(card, seqPrefix, totalFrames, durationMs, value, sym, resolve) {
        const staticBase = _assetUrl(seqPrefix);
        const denomVal = seqPrefix.split('/').pop();
        const filePrefix = (denomVal === '1') ? `${denomVal}cedi` : `${denomVal}cedis`;

        // Clear CSS classes
        card.classList.remove('entering', 'dragging', 'spring-back');
        card.style.transform = '';
        card.style.opacity = '1';

        // Use existing img element to play frames — no overlay
        let frameImg = card.querySelector('img');
        if (!frameImg) {
            card.innerHTML = `<img src="${staticBase}/${filePrefix}_00000.png" alt="flip"
                 style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;border-radius:10px;display:block;" />`;
            frameImg = card.querySelector('img');
        } else {
            frameImg.src = `${staticBase}/${filePrefix}_00000.png`;
        }

        let currentFrame = 0;
        const interval = Math.max(16, Math.floor(durationMs / totalFrames));

        // Preload first few frames
        for (let i = 1; i <= Math.min(5, totalFrames - 1); i++) {
            const img = new Image();
            img.src = `${staticBase}/${filePrefix}_${String(i).padStart(5, '0')}.png`;
        }

        const seqTimer = setInterval(() => {
            currentFrame++;
            if (currentFrame >= totalFrames) {
                clearInterval(seqTimer);

                _noteFlipCount++;
                updateRunningTotal();
                const pile = document.getElementById('note-pile');
                const pileCount = document.getElementById('pile-count');
                if (pile) pile.classList.add('visible');
                if (pileCount) pileCount.textContent = _noteFlipCount;

                setTimeout(() => {
                    card.removeAttribute('id');
                    card.classList.add('to-pile');
                    card.addEventListener('animationend', () => card.remove(), { once: true });
                    _placeReadyCard();
                    state.isFlipping = false;
                    resolve();
                }, 500);
                return;
            }

            if (currentFrame + 3 < totalFrames) {
                const preload = new Image();
                preload.src = `${staticBase}/${filePrefix}_${String(currentFrame + 3).padStart(5, '0')}.png`;
            }
            frameImg.src = `${staticBase}/${filePrefix}_${String(currentFrame).padStart(5, '0')}.png`;
        }, interval);
    }

    // ---- CSS FALLBACK FLIP ANIMATION ----
    // Used when no GIF/video/PNG assets are available.
    // Shows the denomination face image directly on the card with a reveal animation.
    function _flipWithCSS(card, isZero, value, sym, denomData, resolve) {
        card.classList.remove('entering', 'dragging', 'spring-back');
        card.style.transform = '';
        card.style.opacity = '1';

        // Pre-place next card underneath
        if (!isZero) _placeNextCardUnderneath();

        // Build the denomination face content
        const faceUrl = denomData?.face_image_path
            ? _cloudinaryFill(_assetUrl(denomData.face_image_path))
            : (denomData?.front_image_url || null);

        if (faceUrl) {
            card.innerHTML = `<img src="${faceUrl}" alt="${isZero ? 'ZERO' : sym + value}" style="${_imgStyle}opacity:0;" />`;
            // Trigger reveal animation
            requestAnimationFrame(() => {
                const img = card.querySelector('img');
                if (img) { img.style.transition = 'opacity 0.4s ease, transform 0.4s ease'; img.style.opacity = '1'; }
            });
        } else {
            // Minimal text fallback
            const label = isZero ? 'ZERO' : `+${sym}${parseFloat(value).toFixed(2)}`;
            card.innerHTML = `<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:2rem;font-weight:800;color:${isZero ? '#ff4444' : '#ffd700'};text-shadow:0 2px 8px rgba(0,0,0,0.6);">${label}</div>`;
        }

        // Complete after a brief display period
        const displayMs = isZero ? 800 : 600;
        setTimeout(() => {
            _noteFlipCount++;
            if (!isZero) {
                updateRunningTotal();
                const pile = document.getElementById('note-pile');
                const pileCount = document.getElementById('pile-count');
                if (pile) pile.classList.add('visible');
                if (pileCount) pileCount.textContent = _noteFlipCount;
            }

            setTimeout(() => {
                if (!isZero) {
                    const nextCard = document.getElementById('next-note');
                    if (nextCard) nextCard.style.opacity = '1';
                }

                card.removeAttribute('id');
                card.classList.add('to-pile');
                card.addEventListener('animationend', () => card.remove(), { once: true });
                setTimeout(() => { if (card.parentNode) card.remove(); }, 600);

                if (!isZero) {
                    const next = document.getElementById('next-note');
                    if (next) { next.id = 'active-note'; }
                    _startAutoFlipTimer();
                } else {
                    _stopAutoFlipTimer();
                }

                state.isFlipping = false;
                resolve();
            }, isZero ? 600 : 400);
        }, displayMs);
    }

    function updateRunningTotal() {
        const totalEl = document.getElementById('note-running-total');
        const nrtVal = document.getElementById('nrt-value');
        if (!totalEl || !nrtVal) return;
        totalEl.classList.add('visible');

        const sym = state.session?.currency?.symbol || 'GH₵';
        const bal = parseFloat(state.session?.cashout_balance || 0);
        nrtVal.textContent = `${sym}${bal.toFixed(2)}`;
        nrtVal.classList.add('bump');
        setTimeout(() => nrtVal.classList.remove('bump'), 350);
    }

    // ==================== SIGNATURE FEATURES ====================

    // --- 1. CONFETTI PARTICLE SYSTEM ---
    const confettiCanvas = document.createElement('canvas');
    confettiCanvas.id = 'confetti-canvas';
    confettiCanvas.style.cssText = 'position:fixed;inset:0;z-index:99;pointer-events:none;';
    document.body.appendChild(confettiCanvas);
    const confettiCtx = confettiCanvas.getContext('2d');
    let confettiParticles = [];
    let confettiAnimId = null;

    function resizeConfetti() {
        confettiCanvas.width = window.innerWidth;
        confettiCanvas.height = window.innerHeight;
    }
    resizeConfetti();
    window.addEventListener('resize', resizeConfetti);

    function spawnConfetti(count, colors, originY) {
        const cy = originY || confettiCanvas.height * 0.3;
        for (let i = 0; i < count; i++) {
            confettiParticles.push({
                x: confettiCanvas.width * 0.5 + (Math.random() - 0.5) * 200,
                y: cy,
                vx: (Math.random() - 0.5) * 12,
                vy: -Math.random() * 14 - 4,
                w: Math.random() * 8 + 4,
                h: Math.random() * 6 + 3,
                color: colors[Math.floor(Math.random() * colors.length)],
                rot: Math.random() * Math.PI * 2,
                rv: (Math.random() - 0.5) * 0.3,
                gravity: 0.25 + Math.random() * 0.1,
                life: 1,
                decay: 0.008 + Math.random() * 0.006,
            });
        }
        if (!confettiAnimId) tickConfetti();
    }

    function tickConfetti() {
        confettiCtx.clearRect(0, 0, confettiCanvas.width, confettiCanvas.height);
        confettiParticles.forEach(p => {
            p.vy += p.gravity;
            p.x += p.vx;
            p.y += p.vy;
            p.rot += p.rv;
            p.life -= p.decay;
            p.vx *= 0.99;
            confettiCtx.save();
            confettiCtx.translate(p.x, p.y);
            confettiCtx.rotate(p.rot);
            confettiCtx.globalAlpha = Math.max(0, p.life);
            confettiCtx.fillStyle = p.color;
            confettiCtx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
            confettiCtx.restore();
        });
        confettiParticles = confettiParticles.filter(p => p.life > 0 && p.y < confettiCanvas.height + 50);
        if (confettiParticles.length > 0) {
            confettiAnimId = requestAnimationFrame(tickConfetti);
        } else {
            confettiCtx.clearRect(0, 0, confettiCanvas.width, confettiCanvas.height);
            confettiAnimId = null;
        }
    }

    // --- 2. STREAK FIRE SYSTEM ---
    let currentStreak = 0;

    function updateStreakBadge(won) {
        if (won) {
            currentStreak++;
        } else {
            currentStreak = 0;
        }
        const badge = document.getElementById('streak-badge');
        if (!badge) return;

        if (currentStreak >= 2) {
            badge.classList.remove('hidden');
            const fireEmoji = currentStreak >= 7 ? '🔥🔥🔥' : currentStreak >= 5 ? '🔥🔥' : '🔥';
            const label = currentStreak >= 7 ? 'INFERNO!' : currentStreak >= 5 ? 'ON FIRE!' : 'STREAK';
            badge.innerHTML = `${fireEmoji} <span class="streak-count">×${currentStreak}</span> <span class="streak-label">${label}</span>`;
            badge.className = 'streak-badge';
            if (currentStreak >= 7) badge.classList.add('inferno');
            else if (currentStreak >= 5) badge.classList.add('fire');
            else if (currentStreak >= 3) badge.classList.add('hot');
        } else {
            badge.classList.add('hidden');
        }
    }

    // --- 3. HAPTIC FEEDBACK ---
    function haptic(pattern) {
        if (navigator.vibrate) {
            try { navigator.vibrate(pattern); } catch(e) {}
        }
    }

    // --- 4. CASINO SOUND ENGINE (Web Audio API, inline generated) ---
    let audioCtx = null;
    function getAudio() {
        if (!audioCtx) {
            try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch(e) {}
        }
        return audioCtx;
    }

    function playTone(freq, duration, type, vol, ramp) {
        const ctx = getAudio(); if (!ctx) return;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = type || 'sine';
        osc.frequency.setValueAtTime(freq, ctx.currentTime);
        if (ramp) osc.frequency.linearRampToValueAtTime(ramp, ctx.currentTime + duration);
        gain.gain.setValueAtTime(vol || 0.15, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
        osc.connect(gain); gain.connect(ctx.destination);
        osc.start(); osc.stop(ctx.currentTime + duration);
    }

    function sfxFlip() {
        playTone(800, 0.08, 'square', 0.08);
        setTimeout(() => playTone(1200, 0.06, 'square', 0.06), 50);
        setTimeout(() => playTone(600, 0.06, 'square', 0.05), 100);
    }

    function sfxWin() {
        playTone(523, 0.12, 'sine', 0.15);
        setTimeout(() => playTone(659, 0.12, 'sine', 0.15), 100);
        setTimeout(() => playTone(784, 0.15, 'sine', 0.18), 200);
        setTimeout(() => playTone(1047, 0.2, 'sine', 0.12), 320);
    }

    function sfxBigWin() {
        sfxWin();
        setTimeout(() => {
            playTone(1047, 0.15, 'sine', 0.12);
            setTimeout(() => playTone(1319, 0.15, 'sine', 0.12), 80);
            setTimeout(() => playTone(1568, 0.25, 'sine', 0.15), 160);
        }, 450);
    }

    function sfxLoss() {
        playTone(400, 0.15, 'sawtooth', 0.1);
        setTimeout(() => playTone(300, 0.2, 'sawtooth', 0.08), 120);
        setTimeout(() => playTone(200, 0.35, 'sawtooth', 0.06), 250);
    }

    function sfxCashout() {
        for (let i = 0; i < 6; i++) {
            setTimeout(() => playTone(800 + i * 200, 0.1, 'sine', 0.1), i * 60);
        }
        setTimeout(() => playTone(2000, 0.4, 'sine', 0.15), 400);
    }

    // --- 5. SOCIAL PROOF TOASTS ---
    let _socialProofInterval = null;
    let _lastFeedIds = new Set();

    function startSocialProof() {
        _socialProofInterval = setInterval(checkForBigWins, 8000);
    }
    function stopSocialProof() {
        if (_socialProofInterval) { clearInterval(_socialProofInterval); _socialProofInterval = null; }
    }

    async function checkForBigWins() {
        try {
            const resp = await fetch('/api/game/live-feed/');
            if (!resp.ok) return;
            const data = await resp.json();
            const feed = data.feed || [];
            for (const item of feed) {
                const key = `${item.player}-${item.time}`;
                if (_lastFeedIds.has(key)) continue;
                _lastFeedIds.add(key);
                if (_lastFeedIds.size > 100) {
                    const arr = [..._lastFeedIds]; _lastFeedIds = new Set(arr.slice(-60));
                }
                if (item.won && parseFloat(item.amount) >= 10) {
                    showSocialToast(item);
                    break;
                }
            }
        } catch(e) {}
    }

    function showSocialToast(item) {
        const existing = document.getElementById('social-toast');
        if (existing) existing.remove();

        const el = document.createElement('div');
        el.id = 'social-toast';
        el.className = 'social-toast';
        const sym = item.symbol || 'GH₵';
        el.innerHTML = `<span class="social-emoji">🎉</span> <strong>${item.player}</strong> just won <span class="social-amount">${sym}${parseFloat(item.amount).toFixed(2)}</span>!`;
        document.body.appendChild(el);
        setTimeout(() => el.classList.add('show'), 50);
        setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 400); }, 4000);
    }

    // --- ENHANCED CELEBRATIONS ---
    const WIN_COLORS = ['#ffd700', '#ffec8b', '#00e676', '#00bfa6', '#4dd9c0', '#fff'];
    const CASHOUT_COLORS = ['#ffd700', '#ff9800', '#ffeb3b', '#fff176', '#00e676', '#76ff03', '#fff'];
    const LOSS_COLORS = ['#ff6b6b', '#ff4444', '#cc0000', '#990000'];

    function winCelebration() {
        spawnConfetti(35, WIN_COLORS);
        sfxWin();
        haptic([30, 30, 60]);
        updateStreakBadge(true);

        // Three.js green flash
        if (particles && particles.material) {
            const orig = particles.material.opacity;
            particles.material.opacity = 1;
            particles.material.size = 0.12;
            setTimeout(() => { particles.material.opacity = orig; particles.material.size = 0.05; }, 500);
        }
    }

    function bigCashoutCelebration() {
        spawnConfetti(100, CASHOUT_COLORS, confettiCanvas.height * 0.2);
        setTimeout(() => spawnConfetti(80, CASHOUT_COLORS, confettiCanvas.height * 0.15), 200);
        setTimeout(() => spawnConfetti(60, CASHOUT_COLORS, confettiCanvas.height * 0.25), 400);
        sfxCashout();
        haptic([50, 50, 50, 50, 100]);
    }

    function lossBurst() {
        spawnConfetti(15, LOSS_COLORS);
        sfxLoss();
        haptic([100, 50, 200]);
        updateStreakBadge(false);

        // Three.js red flash
        if (scene) {
            const flash = new THREE.PointLight(0xff0000, 3, 20);
            flash.position.set(0, 2, 3);
            scene.add(flash);
            setTimeout(() => scene.remove(flash), 600);
        }
    }

    // Gold particle burst from the note area on win
    function spawnWinParticles() {
        const stage = document.getElementById('note-stage');
        if (!stage) return;
        const rect = stage.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        const colors = ['#ffd700', '#ffeb3b', '#00e676', '#4dd9c0', '#fff'];
        for (let i = 0; i < 12; i++) {
            const p = document.createElement('div');
            p.className = 'win-particle';
            const angle = (Math.PI * 2 * i) / 12 + (Math.random() - 0.5) * 0.5;
            const dist = 30 + Math.random() * 40;
            const x = cx + Math.cos(angle) * dist;
            const y = cy + Math.sin(angle) * dist;
            p.style.left = `${x}px`;
            p.style.top = `${y}px`;
            p.style.background = colors[i % colors.length];
            p.style.animationDuration = `${0.5 + Math.random() * 0.5}s`;
            document.getElementById('game-screen').appendChild(p);
            setTimeout(() => p.remove(), 1000);
        }
    }

    // Red edge flash + screen shake on loss
    function triggerLossEffect() {
        const screen = document.getElementById('game-screen');
        if (!screen) return;
        // Red edge flash
        const flash = document.createElement('div');
        flash.className = 'loss-flash-overlay';
        screen.appendChild(flash);
        setTimeout(() => flash.remove(), 500);
        // Screen shake
        screen.classList.add('shake');
        setTimeout(() => screen.classList.remove('shake'), 300);
    }

    // Gold shimmer on cashout
    function triggerCashoutShimmer() {
        const screen = document.getElementById('game-screen');
        if (!screen) return;
        const shimmer = document.createElement('div');
        shimmer.className = 'cashout-shimmer';
        screen.appendChild(shimmer);
        setTimeout(() => shimmer.remove(), 1300);
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
                // OTP channels — WhatsApp first, SMS second
                const smsBtn = document.querySelector('.channel-btn[data-channel="sms"]');
                const waBtn = document.querySelector('.channel-btn[data-channel="whatsapp"]');
                const channelsEl = document.getElementById('otp-channels');
                if (smsBtn && !methods.sms_otp) smsBtn.style.display = 'none';
                if (waBtn && !methods.whatsapp_otp) waBtn.style.display = 'none';
                // Hide entire phone section if neither SMS nor WhatsApp enabled
                if (!methods.sms_otp && !methods.whatsapp_otp) {
                    document.getElementById('otp-step-1')?.querySelector('.input-group')?.style.setProperty('display', 'none');
                    if (channelsEl) channelsEl.style.display = 'none';
                    document.getElementById('send-otp-btn')?.style.setProperty('display', 'none');
                }
                // Default channel: WhatsApp preferred, SMS fallback
                if (methods.whatsapp_otp) {
                    state.otpChannel = 'whatsapp';
                    document.querySelectorAll('.channel-btn').forEach(b => b.classList.remove('active'));
                    if (waBtn) waBtn.classList.add('active');
                } else if (methods.sms_otp) {
                    state.otpChannel = 'sms';
                    document.querySelectorAll('.channel-btn').forEach(b => b.classList.remove('active'));
                    if (smsBtn) smsBtn.classList.add('active');
                }
                // Alt-auth buttons (Google, Facebook, Email) — shown below divider
                let anyAlt = false;
                if (methods.google) {
                    const g = document.getElementById('btn-google');
                    if (g) g.style.display = '';
                    anyAlt = true;
                }
                if (methods.facebook) {
                    const f = document.getElementById('btn-facebook');
                    if (f) f.style.display = '';
                    anyAlt = true;
                }
                if (methods.email_password) {
                    const e = document.getElementById('btn-email-auth');
                    if (e) e.style.display = '';
                    anyAlt = true;
                }
                if (anyAlt) {
                    const div = document.getElementById('alt-auth-divider');
                    const btns = document.getElementById('alt-auth-buttons');
                    if (div) div.style.display = '';
                    if (btns) btns.style.display = '';
                }
            })
            .catch(() => {}); // Fail silently — buttons stay hidden

        // "Continue with Email" button — switch to email auth step
        document.getElementById('btn-email-auth')?.addEventListener('click', () => {
            document.querySelectorAll('.auth-step').forEach(s => s.classList.remove('active'));
            document.getElementById('email-auth-step')?.classList.add('active');
            showError('');
        });

        // Back to phone from email step
        document.getElementById('back-to-phone-from-email')?.addEventListener('click', () => {
            document.querySelectorAll('.auth-step').forEach(s => s.classList.remove('active'));
            document.getElementById('otp-step-1')?.classList.add('active');
            showError('');
        });

        // Email login
        document.getElementById('email-login-btn')?.addEventListener('click', async () => {
            const email = document.getElementById('email-input')?.value?.trim();
            const password = document.getElementById('password-input')?.value;
            if (!email || !password) { showError('Enter email and password'); return; }

            const btn = document.getElementById('email-login-btn');
            btn.disabled = true; btn.textContent = 'Logging in...';
            try {
                const resp = await fetch(API.base + '/accounts/auth/email/login/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password }),
                });
                const data = await resp.json();
                if (resp.ok) {
                    localStorage.setItem('cf_access', data.access_token);
                    localStorage.setItem('cf_refresh', data.refresh_token);
                    showError('');
                    enterLobby();
                } else {
                    showError(data.error || 'Login failed');
                }
            } catch (e) { showError('Network error'); }
            btn.disabled = false; btn.textContent = 'Log In';
        });

        // Email signup
        document.getElementById('email-signup-btn')?.addEventListener('click', async () => {
            const name = document.getElementById('signup-name-input')?.value?.trim();
            const email = document.getElementById('signup-email-input')?.value?.trim();
            const password = document.getElementById('signup-password-input')?.value;
            if (!email || !password) { showError('Enter email and password'); return; }
            if (password.length < 6) { showError('Password must be at least 6 characters'); return; }

            const btn = document.getElementById('email-signup-btn');
            btn.disabled = true; btn.textContent = 'Creating...';
            try {
                const body = { email, password };
                if (name) body.display_name = name;
                if (state.refCode) body.ref_code = state.refCode;
                const resp = await fetch(API.base + '/accounts/auth/email/signup/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
                const data = await resp.json();
                if (resp.ok) {
                    localStorage.setItem('cf_access', data.access_token);
                    localStorage.setItem('cf_refresh', data.refresh_token);
                    showError('');
                    enterLobby();
                } else {
                    showError(data.error || 'Signup failed');
                }
            } catch (e) { showError('Network error'); }
            btn.disabled = false; btn.textContent = 'Create Account';
        });

        // Switch between login/signup
        document.getElementById('switch-to-signup')?.addEventListener('click', (e) => {
            e.preventDefault();
            document.querySelectorAll('.auth-step').forEach(s => s.classList.remove('active'));
            document.getElementById('email-signup-step')?.classList.add('active');
            showError('');
        });
        document.getElementById('switch-to-login')?.addEventListener('click', (e) => {
            e.preventDefault();
            document.querySelectorAll('.auth-step').forEach(s => s.classList.remove('active'));
            document.getElementById('email-auth-step')?.classList.add('active');
            showError('');
        });

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
                    // If server suggests switching channel, auto-switch and show friendly message
                    if (data.suggest_channel) {
                        const altName = data.suggest_channel === 'whatsapp' ? 'WhatsApp' : 'SMS';
                        state.otpChannel = data.suggest_channel;
                        document.querySelectorAll('.channel-btn').forEach(b => {
                            b.classList.toggle('active', b.dataset.channel === data.suggest_channel);
                        });
                        showError(`${data.error || 'Delivery failed.'} We\u2019ve switched to ${altName} \u2014 tap Send Code again.`);
                    } else {
                        showError(data.error || 'Failed to send OTP. Please try again.');
                    }
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
            showError('');
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
    async function loadGameConfig() {
        try {
            const resp = await fetch('/api/game/config/');
            if (resp.ok) {
                state.gameConfig = await resp.json();
                state.denominations = state.gameConfig.denominations || [];
                _preloadGifFirstFrames();
                const c = state.gameConfig;
                const sym = c.currency?.symbol || 'GH₵';
                // Update CTA hint dynamically
                const ctaHint = document.getElementById('cta-hint');
                if (ctaHint) ctaHint.textContent = `Min ${sym}${parseFloat(c.min_stake).toFixed(0)} to play \u2022 Instant mobile money`;
                // Update stake input min/placeholder
                const stakeInput = document.getElementById('stake-input');
                if (stakeInput) { stakeInput.min = c.min_stake; stakeInput.value = c.min_stake; stakeInput.placeholder = c.min_stake; }
            }
        } catch (e) { /* silent */ }
    }

    async function enterLobby() {
        showScreen('lobby-screen');
        await Promise.all([loadProfile(), loadWalletBalance(), loadGameConfig(), loadFeatureConfig()]);
        startLiveFeed();
        startSocialProof();
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
                const balance = parseFloat(data.balance);
                document.getElementById('lobby-balance').textContent =
                    `${data.currency_symbol}${balance.toFixed(2)}`;

                // Show/hide deposit CTA overlay
                const ctaOverlay = document.getElementById('deposit-cta-overlay');
                if (ctaOverlay) {
                    if (balance <= 0) {
                        const wasHidden = ctaOverlay.classList.contains('hidden');
                        ctaOverlay.classList.remove('hidden');
                        if (wasHidden) sfxDeposit();
                    } else {
                        ctaOverlay.classList.add('hidden');
                    }
                }
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
                    // Show resume banner on lobby instead of auto-entering game
                    const banner = document.getElementById('resume-session-banner');
                    if (banner) {
                        const sym = state.session.currency?.symbol || 'GH₵';
                        const bal = parseFloat(state.session.cashout_balance || 0).toFixed(2);
                        const flips = state.session.flip_count || 0;
                        const status = state.session.status === 'paused' ? 'Paused' : 'Active';
                        document.getElementById('resume-info').textContent =
                            `${status} session: ${flips} flips, ${sym}${bal} balance`;
                        banner.classList.remove('hidden');
                    }
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
                    payout_budget: data.payout_budget || '0.00',
                    remaining_budget: data.payout_budget || '0.00',
                    is_holiday_boosted: data.is_holiday_boosted || false,
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

    let _bestDenom = 0;

    function enterGame() {
        stopLiveFeed();
        stopSocialProof();
        currentStreak = 0;
        _bestDenom = 0;
        showScreen('game-screen');
        initScene();
        updateGameHUD();
        updateSidePanels(true);

        const pauseBtn = document.getElementById('pause-btn');
        if (state.session?.status === 'paused') {
            // Paused session — show resume button, don't init note stage yet
            pauseBtn.textContent = '▶ Resume';
            pauseBtn.disabled = false;
            _stopAutoFlipTimer();
        } else {
            pauseBtn.textContent = '⏸ Pause';
            pauseBtn.disabled = false;
            initNoteStage();
        }
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

    // ==================== SIDE ENGAGEMENT PANELS ====================
    function updateSidePanels(reset) {
        if (!state.session) return;
        const s = state.session;
        const sym = s.currency?.symbol || 'GH₵';
        const flipCount = s.flip_count || 0;
        const cashout = parseFloat(s.cashout_balance || 0);
        const stake = parseFloat(s.stake_amount || 1);

        // Left panel: flip count with pop animation
        const flipEl = document.getElementById('side-flip-count');
        if (flipEl) {
            flipEl.textContent = flipCount;
            if (!reset) {
                flipEl.classList.remove('pop');
                void flipEl.offsetWidth;
                flipEl.classList.add('pop');
            }
        }

        // Left panel: best denomination
        const bestEl = document.getElementById('side-best-denom');
        if (bestEl) {
            bestEl.textContent = _bestDenom > 0 ? `${sym}${_bestDenom.toFixed(0)}` : '--';
            if (_bestDenom > 0) {
                const card = bestEl.closest('.side-stat-card');
                if (card) card.classList.add('highlight');
            }
        }

        // Left panel: streak
        const streakCard = document.getElementById('side-streak-card');
        const streakVal = document.getElementById('side-streak-val');
        if (streakCard && streakVal) {
            if (currentStreak >= 2) {
                streakCard.style.display = '';
                streakVal.textContent = `${currentStreak}🔥`;
            } else {
                streakCard.style.display = 'none';
            }
        }

        // Right panel: multiplier (cashout / stake ratio)
        const multEl = document.getElementById('side-multiplier');
        if (multEl) {
            const ratio = stake > 0 ? (cashout / stake) : 0;
            multEl.textContent = `${ratio.toFixed(1)}×`;
            multEl.classList.remove('hot', 'danger');
            if (ratio >= 3) multEl.classList.add('danger');
            else if (ratio >= 1.5) multEl.classList.add('hot');
        }

        // Right panel: risk meter (visual only, based on flip count)
        const riskFill = document.getElementById('side-risk-fill');
        if (riskFill) {
            // Risk rises with flip count — purely visual, logarithmic curve
            const risk = Math.min(95, Math.max(5, 5 + 90 * (1 - Math.exp(-flipCount * 0.12))));
            riskFill.style.height = `${risk}%`;
        }
    }

    async function doFlip() {
        if (state.isFlipping || !state.session || state.session.status !== 'active') return;
        state.isFlipping = true;

        try {
            const resp = await API.post('/game/flip/', {});
            const data = await resp.json();

            if (!data.success) {
                showToast(data.error || 'Flip failed');
                state.isFlipping = false;
                _startAutoFlipTimer();
                return;
            }

            // Update session state BEFORE animation so running total is correct
            state.session.flip_count = data.flip_number;
            state.session.cashout_balance = data.cashout_balance;
            state.session.remaining_budget = data.remaining_budget || '0.00';

            // isFlipping is managed inside flipNoteAnimation
            state.isFlipping = false;
            await flipNoteAnimation(data.is_zero, data.value, data.denomination);

            if (data.is_zero) {
                // LOSS
                state.session.status = 'lost';
                _stopAutoFlipTimer();
                lossBurst();
                triggerLossEffect();

                // Show zero note first
                const zeroNote = document.getElementById('zero-note');
                zeroNote.classList.remove('hidden');
                zeroNote.classList.add('show');
                
                // Show loss overlay after delay
                setTimeout(() => {
                    zeroNote.classList.remove('show');
                    setTimeout(() => {
                        zeroNote.classList.add('hidden');
                        document.getElementById('loss-stake-amount').textContent =
                            `${state.session.currency?.symbol || 'GH₵'}${parseFloat(state.session.stake_amount).toFixed(2)}`;
                        document.getElementById('loss-overlay').classList.remove('hidden');
                    }, 300);
                }, 1500);
            } else {
                // WIN — denomination shown on the note face itself
                const denomDisplay = document.getElementById('denom-display');
                const denomValue = document.getElementById('denom-value');
                const sym = state.session.currency?.symbol || 'GH₵';
                denomValue.textContent = `+${sym}${parseFloat(data.value).toFixed(2)}`;
                denomDisplay.classList.add('show');
                setTimeout(() => denomDisplay.classList.remove('show'), 1200);

                // Track best denomination
                const denomVal = parseFloat(data.value || 0);
                if (denomVal > _bestDenom) _bestDenom = denomVal;

                winCelebration();
                spawnWinParticles();
                updateGameHUD();
                updateSidePanels(false);

                // Badge notifications
                if (data.new_badges) {
                    data.new_badges.forEach((b, i) => setTimeout(() => showBadgeNotification(b), 1200 + i * 1500));
                }

                // Check for ad
                if (data.ad_due) {
                    showAd();
                }
            }
        } catch (e) {
            showToast('Network error');
            state.isFlipping = false;
            _startAutoFlipTimer();
        }
    }

    async function doCashout() {
        if (!state.session || state.isFlipping) return;
        _stopAutoFlipTimer();

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
                bigCashoutCelebration();
                triggerCashoutShimmer();
                if (data.new_badges) {
                    data.new_badges.forEach((b, i) => setTimeout(() => showBadgeNotification(b), 2000 + i * 1500));
                }
                // Instant MoMo cashout
                _setupInstantMomo(data);
            } else {
                showToast(data.error || 'Cashout failed');
                btn.disabled = false;
            }
        } catch (e) {
            showToast('Network error');
            btn.disabled = false;
        }
    }

    function _setupInstantMomo(cashoutData) {
        const section = document.getElementById('instant-momo-section');
        const hasAccEl = document.getElementById('momo-has-account');
        const noAccEl = document.getElementById('momo-no-account');
        if (!section) return;

        // Reset
        section.style.display = 'none';
        if (hasAccEl) hasAccEl.style.display = 'none';
        if (noAccEl) noAccEl.style.display = 'none';

        if (!cashoutData.instant_cashout_available) return;

        section.style.display = '';
        const cashoutAmount = cashoutData.cashout_amount;

        if (cashoutData.primary_momo_account) {
            const acc = cashoutData.primary_momo_account;
            hasAccEl.style.display = '';
            document.getElementById('instant-momo-name').textContent = acc.verified_name;
            document.getElementById('instant-momo-number').textContent = `${acc.mobile_number} (${acc.network})`;
            const statusEl = document.getElementById('instant-momo-status');
            statusEl.textContent = '';
            statusEl.className = 'momo-status';

            const sendBtn = document.getElementById('instant-momo-send-btn');
            sendBtn.disabled = false;
            sendBtn.textContent = `💸 Send GH₵${parseFloat(cashoutAmount).toFixed(2)} to MoMo`;
            sendBtn.onclick = async () => {
                sendBtn.disabled = true;
                sendBtn.textContent = 'Sending...';
                statusEl.textContent = 'Processing withdrawal...';
                statusEl.className = 'momo-status pending';
                try {
                    const resp = await API.post('/payments/withdraw/', {
                        amount: cashoutAmount,
                        account_id: acc.id,
                    });
                    const d = await resp.json();
                    if (d.success) {
                        statusEl.textContent = `Sent! Funds will arrive in 1-5 minutes.`;
                        statusEl.className = 'momo-status success';
                        sendBtn.textContent = '✅ Sent';
                        loadWalletBalance();
                    } else {
                        statusEl.textContent = d.error || 'Withdrawal failed';
                        statusEl.className = 'momo-status error';
                        sendBtn.disabled = false;
                        sendBtn.textContent = `💸 Retry`;
                    }
                } catch (e) {
                    statusEl.textContent = 'Network error';
                    statusEl.className = 'momo-status error';
                    sendBtn.disabled = false;
                    sendBtn.textContent = `💸 Retry`;
                }
            };
        } else {
            noAccEl.style.display = '';
            const addStatus = document.getElementById('instant-momo-add-status');
            addStatus.textContent = '';
            addStatus.className = 'momo-status';
            const phoneInput = document.getElementById('instant-momo-phone');
            const addBtn = document.getElementById('instant-momo-add-btn');
            if (phoneInput) phoneInput.value = '';
            addBtn.disabled = false;
            addBtn.onclick = async () => {
                const phone = phoneInput?.value?.trim();
                if (!phone || phone.length < 9) {
                    addStatus.textContent = 'Enter a valid phone number';
                    addStatus.className = 'momo-status error';
                    return;
                }
                addBtn.disabled = true;
                addBtn.textContent = 'Verifying...';
                addStatus.textContent = 'Verifying account...';
                addStatus.className = 'momo-status pending';
                try {
                    const resp = await API.post('/payments/momo-accounts/add/', { mobile_number: phone });
                    const d = await resp.json();
                    if (d.success || d.account) {
                        addStatus.textContent = `Verified: ${d.verified_name || d.account?.verified_name || phone}`;
                        addStatus.className = 'momo-status success';
                        // Reload — now show the send button
                        setTimeout(() => {
                            const newAcc = d.account || { id: d.account_id, mobile_number: phone, network: d.network || '', verified_name: d.verified_name || '' };
                            cashoutData.primary_momo_account = newAcc;
                            _setupInstantMomo(cashoutData);
                        }, 1500);
                    } else {
                        addStatus.textContent = d.error || 'Verification failed';
                        addStatus.className = 'momo-status error';
                        addBtn.disabled = false;
                        addBtn.textContent = 'Verify & Add';
                    }
                } catch (e) {
                    addStatus.textContent = 'Network error';
                    addStatus.className = 'momo-status error';
                    addBtn.disabled = false;
                    addBtn.textContent = 'Verify & Add';
                }
            };
        }
    }

    async function doPause() {
        if (!state.session || state.isFlipping) return;

        // If session is paused, this button acts as RESUME
        if (state.session.status === 'paused') {
            try {
                const resp = await API.post('/game/resume/', {});
                const data = await resp.json();
                if (resp.ok) {
                    state.session.status = 'active';
                    const pauseBtn = document.getElementById('pause-btn');
                    pauseBtn.textContent = '⏸ Pause';
                    initNoteStage();
                    showToast('Game resumed!');
                } else {
                    showToast(data.error || 'Resume failed');
                }
            } catch (e) {
                showToast('Network error');
            }
            return;
        }

        _stopAutoFlipTimer();

        // First get pause cost
        try {
            const resp = await API.post('/game/pause/', { confirm: false });
            const data = await resp.json();

            const sym = state.session.currency?.symbol || 'GH₵';
            document.getElementById('pause-balance-display').textContent =
                `${sym}${parseFloat(data.current_balance || state.session.cashout_balance).toFixed(2)}`;
            document.getElementById('pause-cost-display').textContent =
                `${sym}${parseFloat(data.pause_cost || 0).toFixed(2)}`;
            document.getElementById('pause-after-display').textContent =
                `${sym}${parseFloat(data.balance_after_pause || data.remaining_balance || 0).toFixed(2)}`;

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

    function showStakeModalInGame() {
        // Reset session state
        state.session = null;
        document.getElementById('loss-overlay')?.classList.add('hidden');
        document.getElementById('cashout-overlay')?.classList.add('hidden');
        document.getElementById('flip-result-overlay')?.classList.add('hidden');
        
        // Show stake modal in game room
        const modal = document.getElementById('game-stake-modal');
        if (modal) {
            modal.classList.remove('hidden');
            // Focus on stake input
            setTimeout(() => {
                document.getElementById('game-stake-input')?.focus();
            }, 100);
        }
    }

    function returnToLobby() {
        _stopAutoFlipTimer();
        if (animationId) cancelAnimationFrame(animationId);
        state.session = null;
        document.getElementById('loss-overlay')?.classList.add('hidden');
        document.getElementById('cashout-overlay')?.classList.add('hidden');
        document.getElementById('flip-result-overlay')?.classList.add('hidden');
        document.getElementById('game-stake-modal')?.classList.add('hidden');
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

    async function loadDepositAccounts() {
        const container = document.getElementById('dep-saved-accounts');
        const select = document.getElementById('dep-account-select');
        const phoneGroup = document.getElementById('dep-phone-group');
        if (!container || !select) return;

        try {
            const resp = await API.get('/payments/momo-accounts/');
            if (!resp.ok) return;
            const data = await resp.json();
            const accounts = data.accounts || [];

            // Clear previous options except the first
            select.innerHTML = '<option value="">-- Use a new number --</option>';

            if (accounts.length === 0) {
                container.style.display = 'none';
                phoneGroup.style.display = '';
                return;
            }

            accounts.forEach(a => {
                const opt = document.createElement('option');
                opt.value = JSON.stringify(a);
                opt.textContent = `${a.verified_name} - ${a.mobile_number} (${NETWORK_NAMES[a.network] || a.network})`;
                if (a.is_primary) opt.textContent += ' ★';
                select.appendChild(opt);
            });

            container.style.display = '';

            // Auto-select primary account
            const primary = accounts.find(a => a.is_primary) || accounts[0];
            if (primary) {
                select.value = JSON.stringify(primary);
                onDepositAccountSelect(primary);
            }
        } catch (e) {
            container.style.display = 'none';
        }
    }

    function onDepositAccountSelect(account) {
        const phoneGroup = document.getElementById('dep-phone-group');
        const verifyStatus = document.getElementById('dep-verify-status');
        const verifiedInfo = document.getElementById('dep-verified-info');
        const verifiedName = document.getElementById('dep-verified-name');
        const btn = document.getElementById('dep-momo-btn');
        const phoneEl = document.getElementById('dep-phone');

        if (!account) {
            // "Use a new number" selected — show phone input, reset
            phoneGroup.style.display = '';
            resetDepositVerification();
            return;
        }

        // Saved account selected — hide phone input, show verified info
        phoneGroup.style.display = 'none';
        if (verifyStatus) verifyStatus.style.display = 'none';
        verifiedInfo.style.display = 'block';
        verifiedName.textContent = `${account.verified_name} (${NETWORK_NAMES[account.network] || account.network})`;
        document.getElementById('dep-account-id').value = account.id;
        document.getElementById('dep-network').value = account.network;
        if (phoneEl) phoneEl.value = account.mobile_number;
        _lastVerifiedPhone = account.mobile_number.replace(/\D/g, '');
        if (btn) btn.disabled = false;
    }

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
            verifyText.textContent = e?.status === 429 ? 'Too many attempts. Wait a minute and try again.' : 'Could not verify. Check number and try again.';
            verifyStatus.className = 'verify-status error';
        }
    }

    function parseApiError(resp, data) {
        if (resp?.status === 429) return 'Too many requests. Please wait a moment and try again.';
        if (resp?.status === 403) return data?.error || 'Access denied.';
        if (resp?.status === 404) return data?.error || 'Account not found.';
        if (data?.error) return data.error;
        if (data?.detail) return data.detail;
        return 'Something went wrong. Please try again.';
    }

    async function pollDepositStatus(reference, statusEl) {
        const POLL_INTERVAL = 3000;
        const MAX_POLLS = 40; // 40 * 3s = 120 seconds max
        let dots = '';

        for (let i = 0; i < MAX_POLLS; i++) {
            await new Promise(r => setTimeout(r, POLL_INTERVAL));
            dots = '.'.repeat((i % 3) + 1);

            try {
                const resp = await API.get(`/payments/status/deposit/${reference}/`);
                const data = await resp.json();
                const st = (data.status || '').toUpperCase();

                if (st === 'COMPLETED' || st === 'SUCCESSFUL') {
                    statusEl.textContent = 'Payment successful! Your balance has been updated.';
                    statusEl.className = 'status-msg success';
                    await loadWalletBalance();
                    setTimeout(() => hideModal('deposit-modal'), 2000);
                    return;
                }
                if (st === 'FAILED') {
                    statusEl.textContent = data.message || 'Payment failed. Please try again.';
                    statusEl.className = 'status-msg error';
                    return;
                }
                // Still pending/processing
                statusEl.textContent = `Waiting for payment confirmation${dots}`;
                statusEl.className = 'status-msg success';
            } catch (e) {
                // Network hiccup — keep polling
                statusEl.textContent = `Checking payment status${dots}`;
                statusEl.className = 'status-msg';
            }
        }

        // Timeout — do a final balance check in case webhook arrived
        await loadWalletBalance();
        statusEl.textContent = 'Payment is still processing. Your balance will update automatically once confirmed.';
        statusEl.className = 'status-msg';
        setTimeout(() => hideModal('deposit-modal'), 4000);
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
                statusEl.textContent = `Payment prompt sent to ${data.verified_name || 'your phone'}! Approve on your phone.`;
                statusEl.className = 'status-msg success';
                // Disable button during polling
                const depBtn = document.getElementById('dep-momo-btn');
                if (depBtn) depBtn.disabled = true;
                // Poll deposit status until terminal state or timeout
                await pollDepositStatus(data.reference, statusEl);
                if (depBtn) depBtn.disabled = false;
            } else {
                statusEl.textContent = parseApiError(resp, data);
                statusEl.className = 'status-msg error';
            }
        } catch (e) {
            statusEl.textContent = 'Connection failed. Check your internet and try again.';
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
            statusEl.textContent = 'Connection failed. Check your internet and try again.';
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
                statusEl.textContent = 'Withdrawal sent! Funds will arrive in 1-5 minutes.';
                statusEl.className = 'status-msg success';
                setTimeout(() => {
                    hideModal('withdraw-modal');
                    loadWalletBalance();
                }, 4000);
            } else {
                statusEl.textContent = parseApiError(resp, data);
                statusEl.className = 'status-msg error';
            }
        } catch (e) {
            statusEl.textContent = 'Connection failed. Check your internet and try again.';
            statusEl.className = 'status-msg error';
        }
    }

    // ==================== SETTINGS ====================
    const _settingsKey = 'cf_settings';
    let _settings = { sound: true, haptic: true, autoflip: false, autoflipSpeed: 5 };

    function loadSettings() {
        try {
            const saved = JSON.parse(localStorage.getItem(_settingsKey) || '{}');
            _settings = { ..._settings, ...saved };
        } catch (e) {}
    }

    function saveSettings() {
        try { localStorage.setItem(_settingsKey, JSON.stringify(_settings)); } catch (e) {}
    }

    function openSettings() {
        // Populate account info
        if (state.player) {
            const phoneEl = document.getElementById('settings-phone');
            const idEl = document.getElementById('settings-player-id');
            if (phoneEl) phoneEl.textContent = state.player.phone || '—';
            if (idEl) idEl.textContent = (state.player.id || '').substring(0, 12) + '…';
        }
        // Sync toggles to current settings
        const soundEl = document.getElementById('setting-sound');
        const hapticEl = document.getElementById('setting-haptic');
        const autoflipEl = document.getElementById('setting-autoflip');
        const speedEl = document.getElementById('setting-autoflip-speed');
        const speedRow = document.getElementById('autoflip-speed-row');
        if (soundEl) soundEl.checked = _settings.sound;
        if (hapticEl) hapticEl.checked = _settings.haptic;
        if (autoflipEl) autoflipEl.checked = _settings.autoflip;
        if (speedEl) speedEl.value = String(_settings.autoflipSpeed || 5);
        if (speedRow) speedRow.style.display = _settings.autoflip ? '' : 'none';
        showModal('settings-modal');
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

    // ==================== TRANSFER ====================
    function handleTrfPhoneInput() {
        const phone = document.getElementById('trf-phone')?.value?.replace(/\D/g, '') || '';
        const badge = document.getElementById('trf-network-badge');
        const preview = document.getElementById('trf-recipient-preview');
        const nw = detectNetworkFromPhone(phone);
        if (badge) {
            if (nw && phone.length >= 3) {
                badge.textContent = NETWORK_NAMES[nw] || nw;
                badge.className = 'network-badge ' + nw.toLowerCase();
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }
        }
        if (preview) preview.style.display = 'none';
    }

    async function doTransfer() {
        const phone = document.getElementById('trf-phone')?.value?.trim();
        const amount = document.getElementById('trf-amount')?.value;
        const statusEl = document.getElementById('trf-status');
        const btn = document.getElementById('trf-btn');

        if (!phone || !amount) {
            statusEl.textContent = 'Phone and amount required';
            statusEl.className = 'status-msg error';
            return;
        }

        btn.disabled = true;
        btn.textContent = 'Sending...';
        statusEl.textContent = '';

        try {
            const resp = await API.post('/payments/wallet/transfer/', { phone, amount });
            const data = await resp.json();

            if (resp.ok && data.success) {
                statusEl.textContent = data.message;
                statusEl.className = 'status-msg success';
                loadWalletBalance();
                setTimeout(() => {
                    hideModal('transfer-modal');
                    document.getElementById('trf-phone').value = '';
                    document.getElementById('trf-amount').value = '';
                    statusEl.textContent = '';
                }, 2500);
            } else {
                const errMsg = parseApiError(resp, data);
                statusEl.textContent = errMsg;
                statusEl.className = 'status-msg error';
            }
        } catch (e) {
            statusEl.textContent = 'Network error';
            statusEl.className = 'status-msg error';
        }

        btn.disabled = false;
        btn.textContent = 'Send Funds';
    }

    // ==================== FEATURE CONFIG ====================
    let featureFlags = {};

    async function loadFeatureConfig() {
        try {
            const resp = await fetch('/api/game/features/');
            if (resp.ok) featureFlags = await resp.json();
        } catch(e) {}
    }

    // ==================== DAILY BONUS WHEEL ====================
    let wheelSegments = [];
    let wheelAngle = 0;
    let wheelSpinning = false;

    function drawWheel(segments, highlight) {
        const canvas = document.getElementById('wheel-canvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const cx = canvas.width / 2, cy = canvas.height / 2, r = 130;
        const count = segments.length;
        if (count === 0) return;
        const arc = (Math.PI * 2) / count;

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(wheelAngle);

        for (let i = 0; i < count; i++) {
            const angle = i * arc;
            ctx.beginPath();
            ctx.moveTo(0, 0);
            ctx.arc(0, 0, r, angle, angle + arc);
            ctx.closePath();
            ctx.fillStyle = segments[i].color || '#333';
            if (highlight === i) { ctx.fillStyle = '#fff'; }
            ctx.fill();
            ctx.strokeStyle = 'rgba(255,255,255,0.3)';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Label
            ctx.save();
            ctx.rotate(angle + arc / 2);
            ctx.textAlign = 'right';
            ctx.fillStyle = highlight === i ? '#000' : '#fff';
            ctx.font = 'bold 13px Orbitron, sans-serif';
            ctx.fillText(segments[i].label, r - 12, 5);
            ctx.restore();
        }

        // Center circle
        ctx.beginPath();
        ctx.arc(0, 0, 22, 0, Math.PI * 2);
        ctx.fillStyle = '#0D1117';
        ctx.fill();
        ctx.strokeStyle = '#ffd700';
        ctx.lineWidth = 3;
        ctx.stroke();
        ctx.fillStyle = '#ffd700';
        ctx.font = 'bold 11px Orbitron';
        ctx.textAlign = 'center';
        ctx.fillText('CF', 0, 4);

        ctx.restore();
    }

    async function openWheel() {
        showModal('wheel-modal');
        const statusEl = document.getElementById('wheel-status');
        const spinBtn = document.getElementById('spin-btn');
        const resultEl = document.getElementById('wheel-result');
        resultEl.classList.add('hidden');
        statusEl.textContent = '';
        spinBtn.disabled = true;

        try {
            const resp = await API.get('/game/wheel/status/');
            const data = await resp.json();
            wheelSegments = data.segments || [];
            drawWheel(wheelSegments);

            if (!data.enabled) {
                statusEl.textContent = 'Daily wheel is currently disabled';
            } else if (data.available) {
                spinBtn.disabled = false;
                statusEl.textContent = 'Spin to win a bonus!';
                statusEl.className = 'status-msg';
            } else {
                const next = data.next_spin ? new Date(data.next_spin) : null;
                const hrs = next ? Math.max(0, Math.ceil((next - Date.now()) / 3600000)) : 24;
                statusEl.textContent = `Next spin in ~${hrs}h`;
                statusEl.className = 'status-msg';
            }
        } catch(e) {
            statusEl.textContent = 'Error loading wheel';
        }
    }

    async function doSpin() {
        if (wheelSpinning) return;
        const spinBtn = document.getElementById('spin-btn');
        const resultEl = document.getElementById('wheel-result');
        const statusEl = document.getElementById('wheel-status');
        spinBtn.disabled = true;
        wheelSpinning = true;
        statusEl.textContent = '';

        try {
            const resp = await API.post('/game/wheel/spin/', {});
            const data = await resp.json();

            if (!resp.ok || !data.success) {
                statusEl.textContent = data.error || 'Spin failed';
                statusEl.className = 'status-msg error';
                wheelSpinning = false;
                return;
            }

            // Animate spin
            const count = wheelSegments.length;
            const arc = (Math.PI * 2) / count;
            const targetIdx = data.segment_index;
            // We want the pointer (top) to land on targetIdx
            // Pointer is at top (angle 0 = right, so -PI/2 for top)
            const targetAngle = -(targetIdx * arc + arc / 2) - Math.PI / 2;
            const totalSpin = Math.PI * 2 * 6 + targetAngle; // 6 full rotations + target
            const startAngle = wheelAngle;
            const startTime = Date.now();
            const duration = 4000;

            _playFlipSound();

            function animateSpin() {
                const elapsed = Date.now() - startTime;
                const progress = Math.min(elapsed / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                wheelAngle = startAngle + eased * totalSpin;
                drawWheel(wheelSegments);

                if (progress < 1) {
                    requestAnimationFrame(animateSpin);
                } else {
                    // Done
                    wheelSpinning = false;
                    drawWheel(wheelSegments, targetIdx);
                    sfxBigWin();
                    haptic([50, 30, 80]);
                    spawnConfetti(50, CASHOUT_COLORS);

                    resultEl.innerHTML = `🎉 You won <strong>${data.label}</strong>!`;
                    resultEl.classList.remove('hidden');
                    statusEl.textContent = `Credited to your wallet`;
                    statusEl.className = 'status-msg success';
                    loadWalletBalance();
                }
            }
            animateSpin();
        } catch(e) {
            statusEl.textContent = 'Network error';
            statusEl.className = 'status-msg error';
            wheelSpinning = false;
        }
    }

    // ==================== BADGES ====================
    async function loadBadges() {
        const grid = document.getElementById('badges-grid');
        const xpBar = document.getElementById('badges-xp');
        if (!grid) return;

        try {
            const resp = await API.get('/game/badges/');
            const data = await resp.json();
            const badges = data.badges || [];

            xpBar.innerHTML = `<span class="xp-label">⭐ ${data.total_xp} XP</span> <span class="xp-count">${data.earned_count}/${badges.length} earned</span>`;

            grid.innerHTML = badges.map(b => `
                <div class="badge-card ${b.earned ? 'earned' : 'locked'}">
                    <span class="badge-emoji">${b.emoji}</span>
                    <span class="badge-name">${b.name}</span>
                    <span class="badge-desc">${b.description}</span>
                    ${b.earned ? '<span class="badge-check">✓</span>' : '<span class="badge-lock">🔒</span>'}
                </div>
            `).join('');
        } catch(e) {
            grid.innerHTML = '<p class="text-muted">Error loading badges</p>';
        }
    }

    function showBadgeNotification(badge) {
        const el = document.createElement('div');
        el.className = 'badge-notification';
        el.innerHTML = `<span class="badge-notif-emoji">${badge.emoji}</span> <strong>Badge Unlocked!</strong> ${badge.name}`;
        document.body.appendChild(el);
        setTimeout(() => el.classList.add('show'), 50);
        sfxBigWin();
        spawnConfetti(40, ['#ffd700', '#8B5CF6', '#fff', '#00e676']);
        setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 400); }, 4000);
    }

    // ==================== DEPOSIT SOUND ====================
    function sfxDeposit() {
        if (!featureFlags.deposit_sound_enabled) return;
        const ctx = getAudio(); if (!ctx) return;
        // Warm ambient chord: C major 7th
        const freqs = [261, 329, 392, 494];
        freqs.forEach((f, i) => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(f, ctx.currentTime);
            gain.gain.setValueAtTime(0, ctx.currentTime);
            gain.gain.linearRampToValueAtTime(0.06, ctx.currentTime + 0.3 + i * 0.1);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 2.5);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(ctx.currentTime + i * 0.15);
            osc.stop(ctx.currentTime + 2.5);
        });
    }

    // ==================== LIVE FEED ====================

    let _feedInterval = null;

    async function loadLiveFeed() {
        const feedEl = document.getElementById('live-feed');
        if (!feedEl) return;

        try {
            const resp = await fetch('/api/game/live-feed/');
            if (!resp.ok) return;
            const data = await resp.json();
            const items = data.feed || [];

            if (items.length === 0) {
                feedEl.innerHTML = '<div class="feed-placeholder">No games yet — be the first!</div>';
                return;
            }

            feedEl.innerHTML = items.map(item => {
                const cls = item.won ? 'won' : 'lost';
                const icon = item.won ? '🏆' : '💀';
                const label = item.won ? `+${item.symbol}${parseFloat(item.amount).toFixed(2)}` : `-${item.symbol}${parseFloat(item.amount).toFixed(2)}`;
                const ago = item.time ? _timeAgo(new Date(item.time)) : '';
                return `<div class="feed-item">
                    <span class="feed-player">${item.player}</span>
                    <span class="feed-result ${cls}">${icon} ${label}</span>
                    <span class="feed-flips">${item.flips}x</span>
                    <span class="feed-time">${ago}</span>
                </div>`;
            }).join('');
        } catch (e) { /* silent */ }
    }

    function _timeAgo(date) {
        const secs = Math.floor((Date.now() - date.getTime()) / 1000);
        if (secs < 60) return 'now';
        if (secs < 3600) return `${Math.floor(secs / 60)}m`;
        if (secs < 86400) return `${Math.floor(secs / 3600)}h`;
        return `${Math.floor(secs / 86400)}d`;
    }

    function startLiveFeed() {
        loadLiveFeed();
        if (_feedInterval) clearInterval(_feedInterval);
        _feedInterval = setInterval(loadLiveFeed, 5000);
    }

    function stopLiveFeed() {
        if (_feedInterval) { clearInterval(_feedInterval); _feedInterval = null; }
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
                const code = player.referral_code || (player.id || '').substring(0, 8);
                const refLink = window.location.origin + '/?ref=' + code;
                document.getElementById('referral-link').value = refLink;
            }
        } catch (e) { /* ignore */ }

        // Load referral stats
        try {
            const resp = await API.get('/referrals/stats/');
            if (resp.ok) {
                const data = await resp.json();
                const sym = state.session?.currency?.symbol || 'GH₵';
                document.getElementById('ref-total').textContent = data.total_referrals || 0;
                document.getElementById('ref-earned').textContent = `${sym}${parseFloat(data.total_earned || 0).toFixed(2)}`;
                document.getElementById('ref-pending').textContent = data.pending_referrals || 0;
                if (data.referrer_bonus) {
                    document.getElementById('ref-bonus-badge').textContent = `Earn ${sym}${parseFloat(data.referrer_bonus).toFixed(2)} per referral`;
                }
            }
        } catch (e) { /* ignore */ }
    }

    // ==================== EVENT BINDINGS ====================
    function bindEvents() {
        // Start game
        document.getElementById('start-game-btn')?.addEventListener('click', startGame);
        document.getElementById('resume-game-btn')?.addEventListener('click', () => {
            document.getElementById('resume-session-banner')?.classList.add('hidden');
            enterGame();
        });

        // Quick stakes
        document.querySelectorAll('.quick-stake').forEach(btn => {
            btn.addEventListener('click', () => {
                document.getElementById('stake-input').value = btn.dataset.amount;
            });
        });

        // Game buttons (flip is now swipe-triggered, no button)
        document.getElementById('cashout-btn')?.addEventListener('click', doCashout);
        document.getElementById('pause-btn')?.addEventListener('click', doPause);
        document.getElementById('confirm-pause-btn')?.addEventListener('click', confirmPause);
        document.getElementById('game-back-btn')?.addEventListener('click', () => {
            if (state.isFlipping) return;
            if (state.session?.status === 'active') {
                const bal = parseFloat(state.session.cashout_balance || 0);
                const sym = state.session.currency?.symbol || 'GH₵';
                const msgEl = document.getElementById('leave-game-msg');
                const confirmBtn = document.getElementById('confirm-leave-btn');
                if (bal > 0) {
                    msgEl.innerHTML = `You will <strong>LOSE</strong> your current balance of <strong>${sym}${bal.toFixed(2)}</strong> if you leave.<br><br>Use <strong>Cashout</strong> or <strong>Pause</strong> instead to keep your winnings.`;
                    confirmBtn.textContent = 'Leave & Lose Balance';
                    confirmBtn.style.background = '#e74c3c';
                } else {
                    msgEl.textContent = 'Leave the game and return to the lobby?';
                    confirmBtn.textContent = 'Leave Game';
                    confirmBtn.style.background = '';
                }
                showModal('leave-game-modal');
                return;
            }
            returnToLobby();
        });
        document.getElementById('confirm-leave-btn')?.addEventListener('click', () => {
            hideModal('leave-game-modal');
            returnToLobby();
        });

        // Loss/Cashout overlays
        document.getElementById('play-again-btn')?.addEventListener('click', () => {
            document.getElementById('loss-overlay').classList.add('hidden');
            // Stay in game room and show stake modal
            showStakeModalInGame();
        });
        document.getElementById('loss-lobby-btn')?.addEventListener('click', () => {
            document.getElementById('loss-overlay').classList.add('hidden');
            returnToLobby();
        });
        document.getElementById('cashout-lobby-btn')?.addEventListener('click', () => {
            document.getElementById('cashout-overlay').classList.add('hidden');
            returnToLobby();
        });
        document.getElementById('cashout-play-again-btn')?.addEventListener('click', () => {
            document.getElementById('cashout-overlay').classList.add('hidden');
            showStakeModalInGame();
        });

        // Lobby actions
        document.getElementById('deposit-btn')?.addEventListener('click', () => {
            showModal('deposit-modal');
            loadDepositAccounts();
        });
        document.getElementById('cta-deposit-btn')?.addEventListener('click', () => {
            showModal('deposit-modal');
            loadDepositAccounts();
        });
        document.getElementById('header-deposit-btn')?.addEventListener('click', () => {
            showModal('deposit-modal');
            loadDepositAccounts();
        });
        document.getElementById('dep-account-select')?.addEventListener('change', (e) => {
            const val = e.target.value;
            onDepositAccountSelect(val ? JSON.parse(val) : null);
        });
        document.getElementById('withdraw-btn')?.addEventListener('click', () => showModal('withdraw-modal'));
        document.getElementById('transfer-btn')?.addEventListener('click', () => showModal('transfer-modal'));
        document.getElementById('trf-btn')?.addEventListener('click', doTransfer);
        document.getElementById('wheel-btn')?.addEventListener('click', openWheel);
        document.getElementById('spin-btn')?.addEventListener('click', doSpin);
        document.getElementById('badges-btn')?.addEventListener('click', () => {
            showModal('badges-modal');
            loadBadges();
        });
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

        // Username edit
        document.getElementById('edit-name-btn')?.addEventListener('click', () => {
            document.getElementById('profile-name-display').style.display = 'none';
            document.getElementById('profile-name-edit').style.display = 'flex';
            const input = document.getElementById('profile-name-input');
            input.value = state.player?.display_name || '';
            input.focus();
        });
        document.getElementById('cancel-name-btn')?.addEventListener('click', () => {
            document.getElementById('profile-name-edit').style.display = 'none';
            document.getElementById('profile-name-display').style.display = 'flex';
        });
        document.getElementById('save-name-btn')?.addEventListener('click', async () => {
            const newName = document.getElementById('profile-name-input').value.trim();
            if (!newName || newName.length < 2) { alert('Name must be at least 2 characters'); return; }
            try {
                const resp = await API.patch('/accounts/profile/update/', { display_name: newName });
                const data = await resp.json();
                if (resp.ok) {
                    state.player.display_name = newName;
                    document.getElementById('profile-name').textContent = newName;
                    document.getElementById('lobby-player-name').textContent = newName;
                    document.getElementById('profile-name-edit').style.display = 'none';
                    document.getElementById('profile-name-display').style.display = 'flex';
                } else {
                    alert(data.error || data.display_name?.[0] || 'Failed to update name');
                }
            } catch (e) { alert('Network error'); }
        });
        document.getElementById('close-profile')?.addEventListener('click', () => {
            document.getElementById('profile-panel')?.classList.remove('show');
        });
        document.getElementById('profile-deposit-btn')?.addEventListener('click', () => {
            document.getElementById('profile-panel')?.classList.remove('show');
            showModal('deposit-modal');
            loadDepositAccounts();
        });
        document.getElementById('profile-withdraw-btn')?.addEventListener('click', () => {
            document.getElementById('profile-panel')?.classList.remove('show');
            showModal('withdraw-modal');
        });

        // Profile menu items
        document.getElementById('menu-settings')?.addEventListener('click', () => {
            document.getElementById('profile-panel')?.classList.remove('show');
            openSettings();
        });
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

        // Settings modal
        document.getElementById('settings-logout-btn')?.addEventListener('click', () => {
            hideModal('settings-modal');
            logout();
        });
        document.getElementById('setting-sound')?.addEventListener('change', (e) => {
            _settings.sound = e.target.checked;
            saveSettings();
        });
        document.getElementById('setting-haptic')?.addEventListener('change', (e) => {
            _settings.haptic = e.target.checked;
            saveSettings();
        });
        document.getElementById('setting-autoflip')?.addEventListener('change', (e) => {
            _settings.autoflip = e.target.checked;
            saveSettings();
            document.getElementById('autoflip-speed-row').style.display = e.target.checked ? '' : 'none';
        });
        document.getElementById('setting-autoflip-speed')?.addEventListener('change', (e) => {
            _settings.autoflipSpeed = parseInt(e.target.value);
            saveSettings();
        });

        // Transfer phone network detection
        document.getElementById('trf-phone')?.addEventListener('input', handleTrfPhoneInput);

        // Modal close buttons
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', () => hideModal(btn.dataset.modal));
        });

        // Game stake modal (for Play Again)
        document.getElementById('game-stake-input')?.addEventListener('input', (e) => {
            const btn = document.getElementById('game-start-btn');
            const amount = parseFloat(e.target.value);
            btn.disabled = isNaN(amount) || amount < 0.5;
        });

        // Quick stakes in game modal
        document.querySelectorAll('#game-stake-modal .quick-stake').forEach(btn => {
            btn.addEventListener('click', () => {
                document.getElementById('game-stake-input').value = btn.dataset.amount;
                document.getElementById('game-start-btn').disabled = false;
            });
        });

        document.getElementById('game-start-btn')?.addEventListener('click', async () => {
            const stakeInput = document.getElementById('game-stake-input');
            const stake = parseFloat(stakeInput?.value || '1');
            const statusEl = document.getElementById('game-stake-status');
            const btn = document.getElementById('game-start-btn');

            if (isNaN(stake) || stake < 0.5) {
                statusEl.textContent = 'Enter a valid stake amount';
                statusEl.className = 'status-msg error';
                return;
            }

            btn.disabled = true;
            btn.textContent = 'Starting...';
            statusEl.textContent = '';

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
                    hideModal('game-stake-modal');
                    enterGame();
                } else {
                    statusEl.textContent = data.error || 'Failed to start game';
                    statusEl.className = 'status-msg error';
                }
            } catch (e) {
                statusEl.textContent = 'Network error';
                statusEl.className = 'status-msg error';
            }

            btn.disabled = false;
            btn.textContent = '🎰 Start Game';
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
                navigator.clipboard?.writeText(input.value).catch(() => {
                    input.select(); document.execCommand('copy');
                });
                showToast('Link copied! 📋');
            }
        });

        const _getRefMsg = () => {
            const link = document.getElementById('referral-link')?.value || '';
            return `🎰 Play CashFlip & win real money! Use my link to sign up and we both earn a bonus: ${link}`;
        };

        // Share WhatsApp
        document.getElementById('share-whatsapp')?.addEventListener('click', () => {
            window.open(`https://wa.me/?text=${encodeURIComponent(_getRefMsg())}`, '_blank');
        });

        // Share SMS
        document.getElementById('share-sms')?.addEventListener('click', () => {
            window.open(`sms:?body=${encodeURIComponent(_getRefMsg())}`, '_blank');
        });

        // Share Telegram
        document.getElementById('share-telegram')?.addEventListener('click', () => {
            const link = document.getElementById('referral-link')?.value || '';
            window.open(`https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent('🎰 Play CashFlip & win real money!')}`, '_blank');
        });

        // Share Twitter/X
        document.getElementById('share-twitter')?.addEventListener('click', () => {
            const link = document.getElementById('referral-link')?.value || '';
            window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent('🎰 Play CashFlip & win real money! ' + link)}`, '_blank');
        });

        // Share Native (Web Share API)
        document.getElementById('share-native')?.addEventListener('click', async () => {
            const link = document.getElementById('referral-link')?.value || '';
            if (navigator.share) {
                try {
                    await navigator.share({ title: 'CashFlip', text: '🎰 Play CashFlip & win real money!', url: link });
                } catch (e) { /* user cancelled */ }
            } else {
                navigator.clipboard?.writeText(link).catch(() => {});
                showToast('Link copied! Share it anywhere.');
            }
        });

        // Keyboard shortcut for flip (Space / ArrowLeft)
        document.addEventListener('keydown', (e) => {
            if ((e.code === 'Space' || e.code === 'ArrowLeft') && document.getElementById('game-screen')?.classList.contains('active')) {
                e.preventDefault();
                if (state.isFlipping || !state.session || state.session.status !== 'active') return;
                _stopAutoFlipTimer();
                const card = document.getElementById('active-note');
                if (card) {
                    card.classList.remove('entering', 'spring-back', 'dragging');
                    card.style.transform = '';
                    card.classList.add('flipping');
                }
                _hapticHeavy();
                doFlip();
            }
        });
    }

    // ==================== INIT ====================
    // Initialize AudioContext on first user interaction (browser requirement)
    function initAudioOnInteraction() {
        getAudio();
        if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
        document.removeEventListener('touchstart', initAudioOnInteraction);
        document.removeEventListener('click', initAudioOnInteraction);
    }
    document.addEventListener('touchstart', initAudioOnInteraction, { once: true });
    document.addEventListener('click', initAudioOnInteraction, { once: true });

    async function init() {
        loadSettings();
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
