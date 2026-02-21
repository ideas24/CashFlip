import { useEffect, useState } from 'react'
import { Topbar } from '@/components/layout/topbar'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'
import { Save, Shield, Gamepad2, FlaskConical, Plus, Trash2, X, Check, Upload, Image } from 'lucide-react'

interface AuthSettings {
  sms_otp_enabled: boolean
  whatsapp_otp_enabled: boolean
  email_password_enabled: boolean
  google_enabled: boolean
  facebook_enabled: boolean
  otp_expiry_minutes: number
  max_otp_per_hour: number
}

interface SimFeedEntry {
  player: string
  won: boolean
  amount: string
  flips: number
}

interface GameSettings {
  id: number | null
  currency: string
  house_edge_percent: string
  min_deposit: string
  max_cashout: string
  min_stake: string
  pause_cost_percent: string
  zero_base_rate: string
  zero_growth_rate: string
  min_flips_before_zero: number
  min_flips_before_cashout: number
  instant_cashout_enabled: boolean
  instant_cashout_min_amount: string
  max_session_duration_minutes: number
  auto_flip_seconds: number
  flip_animation_mode: string
  flip_display_mode: string
  flip_animation_speed_ms: number
  flip_sound_enabled: boolean
  simulated_feed_enabled: boolean
  simulated_feed_data: SimFeedEntry[]
  is_active: boolean
}

interface SimConfig {
  id: number
  name: string
  is_enabled: boolean
  outcome_mode: string
  outcome_mode_display: string
  force_zero_at_flip: number
  fixed_zero_probability: string
  win_streak_length: number
  force_denomination_value: string
  apply_to_all_players: boolean
  override_min_stake: string
  override_max_cashout: string
  grant_test_balance: string
  auto_disable_after: number
  sessions_used: number
  notes: string
  updated_at: string
}

interface FeatureSettings {
  badges_enabled: boolean
  daily_wheel_enabled: boolean
  sounds_enabled: boolean
  haptics_enabled: boolean
  social_proof_enabled: boolean
  streak_badge_enabled: boolean
  confetti_enabled: boolean
  deposit_sound_enabled: boolean
  social_proof_min_amount: string
}

interface WheelSegment {
  label: string
  value: number
  color: string
  weight: number
}

interface WheelSettings {
  is_enabled: boolean
  segments: WheelSegment[]
  cooldown_hours: number
  max_spins_per_day: number
  require_deposit: boolean
}

interface Denomination {
  id: number | null
  value: string
  payout_multiplier: string
  face_image_path: string
  flip_sequence_prefix: string
  flip_sequence_frames: number
  flip_gif_path: string
  display_order: number
  is_zero: boolean
  is_active: boolean
  weight: number
}

interface BrandingSettings {
  logo_url: string
  logo_icon_url: string
  loading_animation_url: string
  primary_color: string
  secondary_color: string
  accent_color: string
  background_color: string
  tagline: string
  regulatory_logo_url: string
  regulatory_text: string
  age_restriction_text: string
  responsible_gaming_text: string
  show_regulatory_footer: boolean
}

interface OutcomeChoice { value: string; label: string }

interface AllSettings {
  auth: AuthSettings
  game: GameSettings
  features: FeatureSettings
  wheel: WheelSettings
  denominations: Denomination[]
  branding: BrandingSettings
  simulated_configs: SimConfig[]
  outcome_mode_choices: OutcomeChoice[]
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<AllSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [tab, setTab] = useState<'auth' | 'game' | 'denominations' | 'features' | 'wheel' | 'branding' | 'simulated'>('auth')
  const [uploading, setUploading] = useState(false)

  const refresh = () => {
    api.get<AllSettings>('/settings/')
      .then(d => { setSettings(d); setError('') })
      .catch(e => setError(e.message || 'Failed to load settings'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { refresh() }, [])

  const saveSettings = async () => {
    if (!settings) return
    setSaving(true)
    setSaved(false)
    try {
      await api.post('/settings/', { auth: settings.auth, game: settings.game, features: settings.features, wheel: settings.wheel, denominations: settings.denominations, branding: settings.branding })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch {}
    setSaving(false)
  }

  const updateAuth = (key: keyof AuthSettings, value: boolean | number) => {
    if (!settings) return
    setSettings({ ...settings, auth: { ...settings.auth, [key]: value } })
  }

  const updateGame = (key: string, value: string | number | boolean | SimFeedEntry[]) => {
    if (!settings) return
    setSettings({ ...settings, game: { ...settings.game, [key]: value } })
  }

  const updateFeature = (key: keyof FeatureSettings, value: boolean | string) => {
    if (!settings) return
    setSettings({ ...settings, features: { ...settings.features, [key]: value } })
  }

  const updateWheel = (key: keyof WheelSettings, value: boolean | number | WheelSegment[]) => {
    if (!settings) return
    setSettings({ ...settings, wheel: { ...settings.wheel, [key]: value } })
  }

  const updateBranding = (key: keyof BrandingSettings, value: string) => {
    if (!settings) return
    setSettings({ ...settings, branding: { ...settings.branding, [key]: value } })
  }

  const uploadBrandingFile = async (field: string, file: File) => {
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('folder', 'cashflip/branding')
      const resp = await api.upload<{ url: string }>('/settings/cloudinary-upload/', formData)
      if (settings && resp.url) {
        const key = field === 'logo' ? 'logo_url' : field === 'logo_icon' ? 'logo_icon_url' : 'loading_animation_url'
        setSettings({
          ...settings,
          branding: { ...settings.branding, [key]: resp.url }
        })
      }
    } catch {}
    setUploading(false)
  }

  const uploadDenomFile = async (denomIndex: number, field: 'face_image_path' | 'flip_gif_path', file: File) => {
    setUploading(true)
    try {
      const folder = field === 'face_image_path' ? 'cashflip/faces' : 'cashflip/gifs'
      const formData = new FormData()
      formData.append('file', file)
      formData.append('folder', folder)
      const resp = await api.upload<{ url: string }>('/settings/cloudinary-upload/', formData)
      if (settings && resp.url) {
        const denoms = [...settings.denominations]
        denoms[denomIndex] = { ...denoms[denomIndex], [field]: resp.url }
        setSettings({ ...settings, denominations: denoms })
      }
    } catch {}
    setUploading(false)
  }

  const createSimConfig = async () => {
    try {
      await api.post('/settings/simulated/', { name: 'New Test Config', is_enabled: false, outcome_mode: 'normal' })
      refresh()
    } catch {}
  }

  const updateSimConfig = async (id: number, data: Partial<SimConfig>) => {
    try {
      await api.patch(`/settings/simulated/${id}/`, data)
      refresh()
    } catch {}
  }

  const deleteSimConfig = async (id: number, name: string) => {
    if (!confirm(`Delete simulation config "${name}"?`)) return
    try {
      await api.delete(`/settings/simulated/${id}/`)
      refresh()
    } catch {}
  }

  if (loading) {
    return (
      <>
        <Topbar title="Settings" />
        <div className="p-6"><div className="h-64 rounded-xl border border-border bg-card animate-pulse" /></div>
      </>
    )
  }

  if (error && !settings) {
    return (
      <>
        <Topbar title="Settings" />
        <div className="p-6"><Card><CardContent className="py-12 text-center text-danger">{error}</CardContent></Card></div>
      </>
    )
  }

  const s = settings!

  return (
    <>
      <Topbar title="Settings" />
      <div className="p-6 space-y-6">
        {/* Tabs */}
        <div className="flex gap-2 border-b border-border pb-0">
          {[
            { key: 'auth' as const, label: 'Auth', icon: Shield },
            { key: 'game' as const, label: 'Game', icon: Gamepad2 },
            { key: 'denominations' as const, label: 'Denominations', icon: Gamepad2 },
            { key: 'features' as const, label: 'Features', icon: Gamepad2 },
            { key: 'wheel' as const, label: 'Daily Wheel', icon: Gamepad2 },
            { key: 'branding' as const, label: 'Branding', icon: Gamepad2 },
            { key: 'simulated' as const, label: 'Simulation', icon: FlaskConical },
          ].map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors cursor-pointer ${
                tab === t.key ? 'border-primary text-primary' : 'border-transparent text-muted hover:text-white'
              }`}
            >
              <t.icon size={16} /> {t.label}
            </button>
          ))}
        </div>

        {/* ===== AUTH TAB ===== */}
        {tab === 'auth' && (
          <Card>
            <CardHeader>
              <CardTitle>Authentication Methods</CardTitle>
              <CardDescription>Control which login methods are available to players</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {([
                { key: 'sms_otp_enabled' as const, label: 'SMS OTP', desc: 'Login via SMS verification code' },
                { key: 'whatsapp_otp_enabled' as const, label: 'WhatsApp OTP', desc: 'Login via WhatsApp verification code' },
                { key: 'email_password_enabled' as const, label: 'Email / Password', desc: 'Signup & login with email address and password' },
                { key: 'google_enabled' as const, label: 'Google OAuth', desc: 'Login with Google account' },
                { key: 'facebook_enabled' as const, label: 'Facebook OAuth', desc: 'Login with Facebook account' },
              ]).map(item => (
                <div key={item.key} className="flex items-center justify-between py-3 border-b border-border/50 last:border-0">
                  <div>
                    <div className="text-sm font-medium text-white">{item.label}</div>
                    <div className="text-xs text-muted">{item.desc}</div>
                  </div>
                  <button
                    onClick={() => updateAuth(item.key, !s.auth[item.key])}
                    className={`relative w-11 h-6 rounded-full transition-colors cursor-pointer ${
                      s.auth[item.key] ? 'bg-primary' : 'bg-surface-hover'
                    }`}
                  >
                    <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                      s.auth[item.key] ? 'translate-x-5' : ''
                    }`} />
                  </button>
                </div>
              ))}

              <div className="grid grid-cols-2 gap-4 pt-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">OTP Expiry (minutes)</label>
                  <Input type="number" value={s.auth.otp_expiry_minutes}
                    onChange={e => updateAuth('otp_expiry_minutes', parseInt(e.target.value) || 5)} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">Max OTP per hour</label>
                  <Input type="number" value={s.auth.max_otp_per_hour}
                    onChange={e => updateAuth('max_otp_per_hour', parseInt(e.target.value) || 6)} />
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* ===== GAME CONFIG TAB ===== */}
        {tab === 'game' && (
          <>
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Game Engine Configuration</CardTitle>
                    <CardDescription>Core parameters for the provably fair coin flip engine ({s.game.currency})</CardDescription>
                  </div>
                  {s.game.id && <Badge variant={s.game.is_active ? 'success' : 'danger'}>{s.game.is_active ? 'Active' : 'Inactive'}</Badge>}
                </div>
              </CardHeader>
              <CardContent>
                {!s.game.id ? (
                  <div className="text-center py-8 text-muted">
                    <Gamepad2 size={40} className="mx-auto mb-3 opacity-40" />
                    <div className="text-lg mb-1">No game configuration found</div>
                    <div className="text-sm">Create a currency and game config from the Django admin first</div>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* House Edge & Stakes */}
                    <div>
                      <h3 className="text-sm font-semibold text-white mb-3">House Edge & Stakes</h3>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">House Edge (%)</label>
                          <Input type="text" value={s.game.house_edge_percent}
                            onChange={e => updateGame('house_edge_percent', e.target.value)} />
                          <p className="text-xs text-muted mt-1">House retention rate (60 = house keeps 60%)</p>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">Min Stake ({s.game.currency})</label>
                          <Input type="text" value={s.game.min_stake}
                            onChange={e => updateGame('min_stake', e.target.value)} />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">Min Deposit ({s.game.currency})</label>
                          <Input type="text" value={s.game.min_deposit}
                            onChange={e => updateGame('min_deposit', e.target.value)} />
                        </div>
                      </div>
                    </div>

                    {/* Cashout & Pause */}
                    <div>
                      <h3 className="text-sm font-semibold text-white mb-3">Cashout & Pause</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">Max Cashout ({s.game.currency})</label>
                          <Input type="text" value={s.game.max_cashout}
                            onChange={e => updateGame('max_cashout', e.target.value)} />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">Pause Cost (%)</label>
                          <Input type="text" value={s.game.pause_cost_percent}
                            onChange={e => updateGame('pause_cost_percent', e.target.value)} />
                          <p className="text-xs text-muted mt-1">% of cashout balance charged to pause</p>
                        </div>
                      </div>
                    </div>

                    {/* Zero Probability Curve */}
                    <div>
                      <h3 className="text-sm font-semibold text-white mb-3">Zero Probability Curve (Sigmoid)</h3>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">Zero Base Rate</label>
                          <Input type="text" value={s.game.zero_base_rate}
                            onChange={e => updateGame('zero_base_rate', e.target.value)} />
                          <p className="text-xs text-muted mt-1">Base probability of zero (0.05 = 5%)</p>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">Zero Growth Rate (k)</label>
                          <Input type="text" value={s.game.zero_growth_rate}
                            onChange={e => updateGame('zero_growth_rate', e.target.value)} />
                          <p className="text-xs text-muted mt-1">Growth factor for sigmoid curve</p>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">Min Flips Before Zero</label>
                          <Input type="number" value={s.game.min_flips_before_zero}
                            onChange={e => updateGame('min_flips_before_zero', parseInt(e.target.value) || 0)} />
                          <p className="text-xs text-muted mt-1">Guaranteed safe flips</p>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">Min Flips Before Cashout</label>
                          <Input type="number" value={s.game.min_flips_before_cashout}
                            onChange={e => updateGame('min_flips_before_cashout', parseInt(e.target.value) || 0)} />
                          <p className="text-xs text-muted mt-1">Prevents risk-free profit exploit</p>
                        </div>
                      </div>
                    </div>

                    {/* Instant Cashout */}
                    <div>
                      <h3 className="text-sm font-semibold text-white mb-3">Instant MoMo Cashout</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="flex items-center gap-3">
                          <input type="checkbox" checked={s.game.instant_cashout_enabled}
                            onChange={e => updateGame('instant_cashout_enabled', e.target.checked)}
                            className="w-4 h-4 rounded border-border" />
                          <label className="text-xs font-medium text-slate-400">Enable instant MoMo cashout on win screen</label>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">Min Amount for Instant Cashout</label>
                          <Input type="text" value={s.game.instant_cashout_min_amount}
                            onChange={e => updateGame('instant_cashout_min_amount', e.target.value)} />
                          <p className="text-xs text-muted mt-1">Below this amount, only wallet credit</p>
                        </div>
                      </div>
                    </div>

                    {/* Session Limits */}
                    <div>
                      <h3 className="text-sm font-semibold text-white mb-3">Session Limits</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">Max Session Duration (minutes)</label>
                          <Input type="number" value={s.game.max_session_duration_minutes}
                            onChange={e => updateGame('max_session_duration_minutes', parseInt(e.target.value) || 120)} />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">Auto-Flip Timer (seconds)</label>
                          <Input type="number" min="0" max="60" value={s.game.auto_flip_seconds}
                            onChange={e => updateGame('auto_flip_seconds', parseInt(e.target.value) || 0)} />
                          <p className="text-xs text-muted mt-1">Auto-flip if player idles (0 = disabled)</p>
                        </div>
                      </div>
                    </div>

                    {/* Flip Animation Settings */}
                    <div>
                      <h3 className="text-sm font-semibold text-white mb-3">Flip Animation</h3>
                      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">Animation Mode</label>
                          <select value={s.game.flip_animation_mode || 'gif'}
                            onChange={e => updateGame('flip_animation_mode', e.target.value)}
                            className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-white">
                            <option value="gif">GIF Animation</option>
                            <option value="png">PNG Sequence</option>
                          </select>
                          <p className="text-xs text-muted mt-1">GIF = single file per denomination, PNG = frame sequence</p>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">Display Mode</label>
                          <select value={s.game.flip_display_mode || 'face_then_gif'}
                            onChange={e => updateGame('flip_display_mode', e.target.value)}
                            className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-white">
                            <option value="face_then_gif">Face Image then GIF</option>
                            <option value="gif_only">GIF Only (static first frame)</option>
                          </select>
                          <p className="text-xs text-muted mt-1">Face+GIF = show face JPG then flip GIF. GIF Only = use GIF first frame as static card</p>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">Animation Speed (ms)</label>
                          <Input type="number" min="500" max="15000" step="100" value={s.game.flip_animation_speed_ms || 1500}
                            onChange={e => updateGame('flip_animation_speed_ms', parseInt(e.target.value) || 1500)} />
                          <p className="text-xs text-muted mt-1">{((s.game.flip_animation_speed_ms || 1500) / 1000).toFixed(1)}s — controls how long the flip animation plays</p>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">Flip Sound</label>
                          <div className="flex items-center gap-3 mt-2">
                            <button
                              onClick={() => updateGame('flip_sound_enabled', !s.game.flip_sound_enabled)}
                              className={`relative w-11 h-6 rounded-full transition-colors cursor-pointer ${
                                s.game.flip_sound_enabled ? 'bg-emerald-500' : 'bg-slate-600'
                              }`}
                            >
                              <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                                s.game.flip_sound_enabled ? 'translate-x-5' : ''
                              }`} />
                            </button>
                            <span className="text-sm text-slate-300">{s.game.flip_sound_enabled ? 'Sound on' : 'Sound off'}</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Simulated Live Feed */}
                    <div>
                      <h3 className="text-sm font-semibold text-white mb-3">Simulated Live Feed (Demo Mode)</h3>
                      <p className="text-xs text-muted mb-3">Enable fake leaderboard entries for demo/pitching. These mix with real results in the live feed.</p>
                      <div className="flex items-center gap-3 mb-4">
                        <button
                          onClick={() => updateGame('simulated_feed_enabled', !s.game.simulated_feed_enabled)}
                          className={`relative w-11 h-6 rounded-full transition-colors cursor-pointer ${
                            s.game.simulated_feed_enabled ? 'bg-emerald-500' : 'bg-slate-600'
                          }`}
                        >
                          <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                            s.game.simulated_feed_enabled ? 'translate-x-5' : ''
                          }`} />
                        </button>
                        <span className="text-sm text-slate-300">{s.game.simulated_feed_enabled ? 'Enabled — fake entries shown in live feed' : 'Disabled'}</span>
                      </div>

                      {s.game.simulated_feed_enabled && (
                        <div className="space-y-2">
                          {(s.game.simulated_feed_data || []).map((entry: SimFeedEntry, i: number) => (
                            <div key={i} className="flex items-center gap-2 p-2 rounded-lg bg-slate-800/50 border border-slate-700/50">
                              <Input className="w-28" placeholder="Player name" value={entry.player}
                                onChange={e => {
                                  const data = [...(s.game.simulated_feed_data || [])]
                                  data[i] = { ...data[i], player: e.target.value }
                                  updateGame('simulated_feed_data', data)
                                }} />
                              <Input className="w-20" type="text" placeholder="Amount" value={entry.amount}
                                onChange={e => {
                                  const data = [...(s.game.simulated_feed_data || [])]
                                  data[i] = { ...data[i], amount: e.target.value }
                                  updateGame('simulated_feed_data', data)
                                }} />
                              <Input className="w-16" type="number" placeholder="Flips" value={entry.flips}
                                onChange={e => {
                                  const data = [...(s.game.simulated_feed_data || [])]
                                  data[i] = { ...data[i], flips: parseInt(e.target.value) || 3 }
                                  updateGame('simulated_feed_data', data)
                                }} />
                              <button
                                onClick={() => {
                                  const data = [...(s.game.simulated_feed_data || [])]
                                  data[i] = { ...data[i], won: !data[i].won }
                                  updateGame('simulated_feed_data', data)
                                }}
                                className={`px-2 py-1 rounded text-xs font-bold cursor-pointer ${
                                  entry.won ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                                }`}
                              >{entry.won ? 'WIN' : 'LOSS'}</button>
                              <button onClick={() => {
                                const data = [...(s.game.simulated_feed_data || [])]
                                data.splice(i, 1)
                                updateGame('simulated_feed_data', data)
                              }} className="text-red-400 hover:text-red-300 cursor-pointer"><Trash2 size={14} /></button>
                            </div>
                          ))}
                          <button onClick={() => {
                            const data = [...(s.game.simulated_feed_data || []), { player: `Lu**yF${Math.floor(Math.random()*90+10)}`, won: true, amount: `${Math.floor(Math.random()*50+5)}.00`, flips: Math.floor(Math.random()*6+2) }]
                            updateGame('simulated_feed_data', data)
                          }} className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white cursor-pointer">
                            <Plus size={14} /> Add simulated entry
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </>
        )}

        {/* ===== DENOMINATIONS TAB ===== */}
        {tab === 'denominations' && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Currency Denominations</CardTitle>
                  <CardDescription>Configure banknote denominations, payout multipliers, and flip animation assets ({s.game.currency})</CardDescription>
                </div>
                <Button size="sm" onClick={() => {
                  const denoms = [...(s.denominations || []), {
                    id: null, value: '1.00', payout_multiplier: '8.00',
                    face_image_path: '', flip_sequence_prefix: '', flip_sequence_frames: 31, flip_gif_path: '',
                    display_order: (s.denominations?.length || 0), is_zero: false, is_active: true, weight: 10
                  }]
                  setSettings({ ...s, denominations: denoms })
                }}><Plus size={14} className="mr-1" /> Add Denomination</Button>
              </div>
            </CardHeader>
            <CardContent>
              {(!s.denominations || s.denominations.length === 0) ? (
                <div className="text-center py-8 text-muted">
                  <Gamepad2 size={40} className="mx-auto mb-3 opacity-40" />
                  <div className="text-lg mb-1">No denominations configured</div>
                  <div className="text-sm">Add denominations for the active currency</div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-sm text-amber-300">
                    <strong>House Edge Math:</strong> Avg payout multiplier × expected flips (~5) should be &lt; 100% for house profit.
                    E.g., avg multiplier 8% × 5 flips = 40% payout → 60% house edge.
                  </div>
                  {s.denominations.map((denom, i) => (
                    <div key={i} className={`p-4 rounded-lg border ${
                      denom.is_zero ? 'bg-red-500/10 border-red-500/30' : 'bg-card border-border'
                    }`}>
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <span className="text-white font-bold">
                            {denom.is_zero ? '🚫 ZERO (Loss)' : `GH₵${denom.value}`}
                          </span>
                          {denom.is_active
                            ? <Badge variant="success">Active</Badge>
                            : <Badge variant="danger">Inactive</Badge>
                          }
                        </div>
                        <div className="flex items-center gap-2">
                          <button onClick={() => {
                            const denoms = [...s.denominations]
                            denoms[i] = { ...denom, is_active: !denom.is_active }
                            setSettings({ ...s, denominations: denoms })
                          }} className={`w-10 h-5 rounded-full transition-colors cursor-pointer ${
                            denom.is_active ? 'bg-emerald-500' : 'bg-zinc-600'
                          }`}>
                            <div className={`w-4 h-4 bg-white rounded-full transition-transform ${
                              denom.is_active ? 'translate-x-5' : 'translate-x-0.5'
                            }`} />
                          </button>
                          <button onClick={() => {
                            const denoms = s.denominations.filter((_, j) => j !== i)
                            setSettings({ ...s, denominations: denoms })
                          }} className="text-red-400 hover:text-red-300 cursor-pointer"><Trash2 size={14} /></button>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <div>
                          <label className="block text-xs text-slate-400 mb-1">Face Value</label>
                          <Input type="text" value={denom.value} onChange={e => {
                            const denoms = [...s.denominations]
                            denoms[i] = { ...denom, value: e.target.value }
                            setSettings({ ...s, denominations: denoms })
                          }} />
                        </div>
                        <div>
                          <label className="block text-xs text-slate-400 mb-1">Payout Multiplier (%)</label>
                          <Input type="text" value={denom.payout_multiplier} onChange={e => {
                            const denoms = [...s.denominations]
                            denoms[i] = { ...denom, payout_multiplier: e.target.value }
                            setSettings({ ...s, denominations: denoms })
                          }} />
                          <p className="text-[10px] text-muted mt-0.5">% of stake per flip</p>
                        </div>
                        <div>
                          <label className="block text-xs text-slate-400 mb-1">Weight</label>
                          <Input type="number" value={denom.weight} onChange={e => {
                            const denoms = [...s.denominations]
                            denoms[i] = { ...denom, weight: parseInt(e.target.value) || 1 }
                            setSettings({ ...s, denominations: denoms })
                          }} />
                          <p className="text-[10px] text-muted mt-0.5">Higher = more frequent</p>
                        </div>
                        <div>
                          <label className="block text-xs text-slate-400 mb-1">Display Order</label>
                          <Input type="number" value={denom.display_order} onChange={e => {
                            const denoms = [...s.denominations]
                            denoms[i] = { ...denom, display_order: parseInt(e.target.value) || 0 }
                            setSettings({ ...s, denominations: denoms })
                          }} />
                        </div>
                      </div>
                      {!denom.is_zero && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
                          {/* Face Image */}
                          <div className="p-3 rounded-lg border border-border/50 bg-zinc-900/50">
                            <label className="block text-xs text-slate-400 mb-2 font-medium">Face Image (static first frame)</label>
                            {denom.face_image_path && (
                              <div className="mb-2 rounded overflow-hidden border border-border bg-black" style={{maxHeight: 80}}>
                                <img src={denom.face_image_path.startsWith('http') ? denom.face_image_path : `/static/${denom.face_image_path}`}
                                  alt="face" className="w-full h-20 object-cover" />
                              </div>
                            )}
                            <div className="flex items-center gap-2">
                              <Input type="text" placeholder="Cloudinary URL or static path" value={denom.face_image_path}
                                className="text-xs flex-1" onChange={e => {
                                const denoms = [...s.denominations]
                                denoms[i] = { ...denom, face_image_path: e.target.value }
                                setSettings({ ...s, denominations: denoms })
                              }} />
                              <label className="shrink-0">
                                <span className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-primary/20 text-primary text-xs rounded cursor-pointer hover:bg-primary/30 transition">
                                  <Upload size={12} /> {uploading ? '...' : 'Upload'}
                                </span>
                                <input type="file" className="hidden" accept="image/*" disabled={uploading}
                                  onChange={e => {
                                    const file = e.target.files?.[0]
                                    if (file) uploadDenomFile(i, 'face_image_path', file)
                                    e.target.value = ''
                                  }} />
                              </label>
                            </div>
                          </div>
                          {/* Flip GIF */}
                          <div className="p-3 rounded-lg border border-border/50 bg-zinc-900/50">
                            <label className="block text-xs text-slate-400 mb-2 font-medium">Flip Animation GIF</label>
                            {denom.flip_gif_path && (
                              <div className="mb-2 rounded overflow-hidden border border-border bg-black" style={{maxHeight: 80}}>
                                <img src={denom.flip_gif_path.startsWith('http') ? denom.flip_gif_path : `/static/${denom.flip_gif_path}`}
                                  alt="flip gif" className="w-full h-20 object-cover" />
                              </div>
                            )}
                            <div className="flex items-center gap-2">
                              <Input type="text" placeholder="Cloudinary URL or static path" value={denom.flip_gif_path}
                                className="text-xs flex-1" onChange={e => {
                                const denoms = [...s.denominations]
                                denoms[i] = { ...denom, flip_gif_path: e.target.value }
                                setSettings({ ...s, denominations: denoms })
                              }} />
                              <label className="shrink-0">
                                <span className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-amber-500/20 text-amber-400 text-xs rounded cursor-pointer hover:bg-amber-500/30 transition">
                                  <Upload size={12} /> {uploading ? '...' : 'Upload'}
                                </span>
                                <input type="file" className="hidden" accept="image/gif" disabled={uploading}
                                  onChange={e => {
                                    const file = e.target.files?.[0]
                                    if (file) uploadDenomFile(i, 'flip_gif_path', file)
                                    e.target.value = ''
                                  }} />
                              </label>
                            </div>
                          </div>
                        </div>
                      )}
                      <div className="flex items-center gap-2 mt-2">
                        <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                          <input type="checkbox" checked={denom.is_zero} onChange={e => {
                            const denoms = [...s.denominations]
                            denoms[i] = { ...denom, is_zero: e.target.checked }
                            setSettings({ ...s, denominations: denoms })
                          }} className="accent-red-500" />
                          Zero (Loss) denomination
                        </label>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* ===== FEATURES TAB ===== */}
        {tab === 'features' && (
          <Card>
            <CardHeader>
              <CardTitle>Feature Toggles</CardTitle>
              <CardDescription>Enable or disable game features globally</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {([
                ['badges_enabled', 'Achievement Badges', 'Player badge/achievement system'],
                ['daily_wheel_enabled', 'Daily Bonus Wheel', 'Free daily spin for bonuses'],
                ['sounds_enabled', 'Casino Sounds', 'Sound effects on flip, win, loss, cashout'],
                ['haptics_enabled', 'Haptic Feedback', 'Mobile vibration on game events'],
                ['social_proof_enabled', 'Social Proof Toasts', 'Show "X just won" notifications'],
                ['streak_badge_enabled', 'Streak Fire Badge', 'Consecutive win streak display'],
                ['confetti_enabled', 'Confetti Particles', 'Win/loss particle effects'],
                ['deposit_sound_enabled', 'Deposit CTA Sound', 'Soothing ambient sound on deposit overlay'],
              ] as [keyof FeatureSettings, string, string][]).map(([key, label, desc]) => (
                <div key={key} className="flex items-center justify-between p-3 rounded-lg bg-card border border-border">
                  <div>
                    <p className="text-sm font-medium text-white">{label}</p>
                    <p className="text-xs text-muted">{desc}</p>
                  </div>
                  <button
                    onClick={() => updateFeature(key, !s.features[key])}
                    className={`w-12 h-6 rounded-full transition-colors ${s.features[key] ? 'bg-primary' : 'bg-zinc-700'}`}
                  >
                    <div className={`w-5 h-5 bg-white rounded-full transition-transform ${s.features[key] ? 'translate-x-6' : 'translate-x-0.5'}`} />
                  </button>
                </div>
              ))}
              <div className="flex items-center gap-3 p-3 rounded-lg bg-card border border-border">
                <div className="flex-1">
                  <p className="text-sm font-medium text-white">Social Proof Min Amount</p>
                  <p className="text-xs text-muted">Minimum win to trigger social proof toast</p>
                </div>
                <Input
                  type="number" step="1" min="1" className="w-24"
                  value={s.features.social_proof_min_amount}
                  onChange={e => updateFeature('social_proof_min_amount', e.target.value)}
                />
              </div>
            </CardContent>
          </Card>
        )}

        {/* ===== DAILY WHEEL TAB ===== */}
        {tab === 'wheel' && (
          <Card>
            <CardHeader>
              <CardTitle>Daily Bonus Wheel</CardTitle>
              <CardDescription>Configure the daily spin wheel segments and rules</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-3 rounded-lg bg-card border border-border">
                <div>
                  <p className="text-sm font-medium text-white">Wheel Enabled</p>
                </div>
                <button
                  onClick={() => updateWheel('is_enabled', !s.wheel.is_enabled)}
                  className={`w-12 h-6 rounded-full transition-colors ${s.wheel.is_enabled ? 'bg-primary' : 'bg-zinc-700'}`}
                >
                  <div className={`w-5 h-5 bg-white rounded-full transition-transform ${s.wheel.is_enabled ? 'translate-x-6' : 'translate-x-0.5'}`} />
                </button>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs text-muted">Cooldown (hours)</label>
                  <Input type="number" min="1" value={s.wheel.cooldown_hours} onChange={e => updateWheel('cooldown_hours', parseInt(e.target.value) || 24)} />
                </div>
                <div>
                  <label className="text-xs text-muted">Max Spins/Day</label>
                  <Input type="number" min="1" value={s.wheel.max_spins_per_day} onChange={e => updateWheel('max_spins_per_day', parseInt(e.target.value) || 1)} />
                </div>
                <div className="flex items-end">
                  <label className="flex items-center gap-2 text-sm text-white cursor-pointer">
                    <input type="checkbox" checked={s.wheel.require_deposit} onChange={e => updateWheel('require_deposit', e.target.checked)} className="accent-primary" />
                    Require deposit
                  </label>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-white">Wheel Segments</p>
                  <Button size="sm" variant="outline" onClick={() => {
                    const segs = [...s.wheel.segments, { label: '₵1.00', value: 1, color: '#ffd700', weight: 10 }]
                    updateWheel('segments', segs)
                  }}><Plus size={14} className="mr-1" /> Add</Button>
                </div>
                <div className="space-y-2">
                  {s.wheel.segments.map((seg, i) => (
                    <div key={i} className="flex items-center gap-2 p-2 rounded bg-zinc-800 border border-border">
                      <input type="color" value={seg.color} className="w-8 h-8 rounded cursor-pointer border-0"
                        onChange={e => { const segs = [...s.wheel.segments]; segs[i] = { ...seg, color: e.target.value }; updateWheel('segments', segs) }} />
                      <Input className="w-24" placeholder="Label" value={seg.label}
                        onChange={e => { const segs = [...s.wheel.segments]; segs[i] = { ...seg, label: e.target.value }; updateWheel('segments', segs) }} />
                      <Input type="number" className="w-20" placeholder="Value" step="0.1" value={seg.value}
                        onChange={e => { const segs = [...s.wheel.segments]; segs[i] = { ...seg, value: parseFloat(e.target.value) || 0 }; updateWheel('segments', segs) }} />
                      <Input type="number" className="w-20" placeholder="Weight" value={seg.weight}
                        onChange={e => { const segs = [...s.wheel.segments]; segs[i] = { ...seg, weight: parseInt(e.target.value) || 1 }; updateWheel('segments', segs) }} />
                      <span className="text-xs text-muted whitespace-nowrap">wt:{seg.weight}</span>
                      <button className="text-red-400 hover:text-red-300" onClick={() => {
                        const segs = s.wheel.segments.filter((_, j) => j !== i)
                        updateWheel('segments', segs)
                      }}><Trash2 size={14} /></button>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* ===== BRANDING TAB ===== */}
        {tab === 'branding' && (
          <Card>
            <CardHeader>
              <CardTitle>Branding & Appearance</CardTitle>
              <CardDescription>Upload logos, favicon, and configure brand colors for both the main site and admin console</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* File uploads */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {[
                  { field: 'logo', label: 'Main Logo', url: s.branding?.logo_url, hint: 'SVG/PNG, displayed in header & auth screens' },
                  { field: 'logo_icon', label: 'Favicon / App Icon', url: s.branding?.logo_icon_url, hint: 'Square SVG/PNG, used as favicon & PWA icon' },
                  { field: 'loading_animation', label: 'Loading Animation', url: s.branding?.loading_animation_url, hint: 'GIF/SVG shown during loading screens' },
                ].map(item => (
                  <div key={item.field} className="p-4 rounded-lg border border-border bg-card">
                    <p className="text-sm font-medium text-white mb-1">{item.label}</p>
                    <p className="text-[10px] text-muted mb-3">{item.hint}</p>
                    {item.url && (
                      <div className="mb-3 p-2 bg-zinc-900 rounded border border-border flex items-center justify-center" style={{minHeight: 80}}>
                        <img src={item.url} alt={item.label} className="max-h-16 max-w-full object-contain" />
                      </div>
                    )}
                    <label className="block">
                      <span className="inline-flex items-center gap-1 px-3 py-1.5 bg-primary/20 text-primary text-xs rounded cursor-pointer hover:bg-primary/30 transition">
                        {uploading ? 'Uploading...' : 'Upload'}
                      </span>
                      <input type="file" className="hidden" accept="image/*,.svg" disabled={uploading}
                        onChange={e => {
                          const file = e.target.files?.[0]
                          if (file) uploadBrandingFile(item.field, file)
                          e.target.value = ''
                        }} />
                    </label>
                  </div>
                ))}
              </div>

              {/* Brand colors */}
              <div>
                <h3 className="text-sm font-medium text-white mb-3">Brand Colors</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {([
                    { key: 'primary_color' as const, label: 'Primary (Teal)', desc: 'Main accent color' },
                    { key: 'secondary_color' as const, label: 'Secondary (Gold)', desc: 'Win highlights' },
                    { key: 'accent_color' as const, label: 'Accent (Lime)', desc: 'Success states' },
                    { key: 'background_color' as const, label: 'Background', desc: 'Page background' },
                  ]).map(item => (
                    <div key={item.key} className="p-3 rounded-lg border border-border bg-card">
                      <p className="text-xs font-medium text-white mb-0.5">{item.label}</p>
                      <p className="text-[10px] text-muted mb-2">{item.desc}</p>
                      <div className="flex items-center gap-2">
                        <input type="color" value={s.branding?.[item.key] || '#000000'}
                          onChange={e => updateBranding(item.key, e.target.value)}
                          className="w-8 h-8 rounded border border-border cursor-pointer" />
                        <Input value={s.branding?.[item.key] || ''} onChange={e => updateBranding(item.key, e.target.value)}
                          className="font-mono text-xs" placeholder="#000000" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Tagline */}
              <div>
                <label className="block text-sm font-medium text-white mb-1">Tagline</label>
                <Input value={s.branding?.tagline || ''} onChange={e => updateBranding('tagline', e.target.value)}
                  placeholder="Flip Notes. Stack Cash. Win Big." />
                <p className="text-[10px] text-muted mt-1">Displayed on auth/loading screens</p>
              </div>

              {/* Regulatory Footer */}
              <div className="border-t border-border pt-4 mt-4">
                <h3 className="text-sm font-semibold text-white mb-3">Regulatory Footer</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="flex items-center gap-3">
                    <input type="checkbox" checked={s.branding?.show_regulatory_footer ?? true}
                      onChange={e => updateBranding('show_regulatory_footer', e.target.checked)}
                      className="w-4 h-4 rounded border-border" />
                    <label className="text-xs font-medium text-slate-400">Show regulatory footer on auth screen</label>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">Regulatory Logo</label>
                    {s.branding?.regulatory_logo_url && (
                      <img src={s.branding.regulatory_logo_url} alt="Regulatory" className="h-8 mb-2 rounded" />
                    )}
                    <input type="file" accept="image/*"
                      onChange={async (e) => {
                        const file = e.target.files?.[0]; if (!file) return;
                        setUploading(true);
                        const fd = new FormData(); fd.append('regulatory_logo', file);
                        try {
                          const res = await api.upload('/settings/branding/upload/', fd);
                          if (res.regulatory_logo_url) updateBranding('regulatory_logo_url', res.regulatory_logo_url);
                        } catch {} finally { setUploading(false); }
                      }}
                      className="text-xs text-slate-400" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">Regulatory Text</label>
                    <Input value={s.branding?.regulatory_text || ''} onChange={e => updateBranding('regulatory_text', e.target.value)}
                      placeholder="Regulated by the Gaming Commission of Ghana" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">Age Restriction</label>
                    <Input value={s.branding?.age_restriction_text || ''} onChange={e => updateBranding('age_restriction_text', e.target.value)}
                      placeholder="18+" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">Responsible Gaming Text</label>
                    <Input value={s.branding?.responsible_gaming_text || ''} onChange={e => updateBranding('responsible_gaming_text', e.target.value)}
                      placeholder="Bet Responsibly" />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* ===== SIMULATED / TESTING TAB ===== */}
        {tab === 'simulated' && (
          <>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-white">Simulation & Test Configs</h2>
                <p className="text-sm text-muted">Override game outcomes for testing. Only one config can be active at a time.</p>
              </div>
              <Button onClick={createSimConfig}>
                <Plus size={16} /> New Config
              </Button>
            </div>

            {s.simulated_configs.length === 0 ? (
              <Card>
                <CardContent className="py-12 text-center text-muted">
                  <FlaskConical size={40} className="mx-auto mb-3 opacity-40" />
                  <div className="text-lg mb-1">No simulation configs</div>
                  <div className="text-sm">Click "New Config" to create a test scenario</div>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                {s.simulated_configs.map(sc => (
                  <Card key={sc.id} className={sc.is_enabled ? 'border-warning/40' : ''}>
                    <CardHeader className="flex flex-row items-center justify-between">
                      <div className="flex items-center gap-3">
                        <FlaskConical size={20} className={sc.is_enabled ? 'text-warning' : 'text-muted'} />
                        <div>
                          <CardTitle className="text-base">{sc.name}</CardTitle>
                          <p className="text-xs text-muted">{sc.outcome_mode_display} &middot; {sc.sessions_used} sessions used</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={sc.is_enabled ? 'warning' : 'default'}>
                          {sc.is_enabled ? 'ACTIVE' : 'Off'}
                        </Badge>
                        <button
                          onClick={() => updateSimConfig(sc.id, { is_enabled: !sc.is_enabled })}
                          className={`relative w-11 h-6 rounded-full transition-colors cursor-pointer ${
                            sc.is_enabled ? 'bg-warning' : 'bg-surface-hover'
                          }`}
                        >
                          <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                            sc.is_enabled ? 'translate-x-5' : ''
                          }`} />
                        </button>
                        <Button variant="ghost" size="sm" onClick={() => deleteSimConfig(sc.id, sc.name)}>
                          <Trash2 size={14} className="text-danger" />
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div>
                            <label className="block text-xs font-medium text-slate-400 mb-1.5">Config Name</label>
                            <Input value={sc.name}
                              onBlur={e => { if (e.target.value !== sc.name) updateSimConfig(sc.id, { name: e.target.value }) }}
                              onChange={e => {
                                const updated = s.simulated_configs.map(c => c.id === sc.id ? { ...c, name: e.target.value } : c)
                                setSettings({ ...s, simulated_configs: updated })
                              }} />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-slate-400 mb-1.5">Outcome Mode</label>
                            <select value={sc.outcome_mode}
                              onChange={e => updateSimConfig(sc.id, { outcome_mode: e.target.value })}
                              className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-white">
                              {s.outcome_mode_choices.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                            </select>
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-slate-400 mb-1.5">Auto-Disable After (sessions)</label>
                            <Input type="number" value={sc.auto_disable_after}
                              onChange={e => updateSimConfig(sc.id, { auto_disable_after: parseInt(e.target.value) || 0 })} />
                          </div>
                        </div>

                        {/* Mode-specific fields */}
                        {sc.outcome_mode === 'force_zero_at' && (
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <label className="block text-xs font-medium text-slate-400 mb-1.5">Force Zero at Flip #</label>
                              <Input type="number" value={sc.force_zero_at_flip}
                                onChange={e => updateSimConfig(sc.id, { force_zero_at_flip: parseInt(e.target.value) || 0 })} />
                            </div>
                          </div>
                        )}
                        {sc.outcome_mode === 'fixed_probability' && (
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <label className="block text-xs font-medium text-slate-400 mb-1.5">Fixed Zero Probability (0.0-1.0)</label>
                              <Input type="text" value={sc.fixed_zero_probability}
                                onBlur={e => updateSimConfig(sc.id, { fixed_zero_probability: e.target.value })}
                                onChange={e => {
                                  const updated = s.simulated_configs.map(c => c.id === sc.id ? { ...c, fixed_zero_probability: e.target.value } : c)
                                  setSettings({ ...s, simulated_configs: updated })
                                }} />
                            </div>
                          </div>
                        )}
                        {sc.outcome_mode === 'streak_then_lose' && (
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <label className="block text-xs font-medium text-slate-400 mb-1.5">Win Streak Length</label>
                              <Input type="number" value={sc.win_streak_length}
                                onChange={e => updateSimConfig(sc.id, { win_streak_length: parseInt(e.target.value) || 1 })} />
                            </div>
                          </div>
                        )}

                        {/* Advanced fields */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div>
                            <label className="block text-xs font-medium text-slate-400 mb-1.5">Force Denomination Value</label>
                            <Input type="text" value={sc.force_denomination_value} placeholder="blank = random"
                              onBlur={e => updateSimConfig(sc.id, { force_denomination_value: e.target.value })}
                              onChange={e => {
                                const updated = s.simulated_configs.map(c => c.id === sc.id ? { ...c, force_denomination_value: e.target.value } : c)
                                setSettings({ ...s, simulated_configs: updated })
                              }} />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-slate-400 mb-1.5">Override Min Stake</label>
                            <Input type="text" value={sc.override_min_stake} placeholder="blank = use default"
                              onBlur={e => updateSimConfig(sc.id, { override_min_stake: e.target.value })}
                              onChange={e => {
                                const updated = s.simulated_configs.map(c => c.id === sc.id ? { ...c, override_min_stake: e.target.value } : c)
                                setSettings({ ...s, simulated_configs: updated })
                              }} />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-slate-400 mb-1.5">Override Max Cashout</label>
                            <Input type="text" value={sc.override_max_cashout} placeholder="blank = use default"
                              onBlur={e => updateSimConfig(sc.id, { override_max_cashout: e.target.value })}
                              onChange={e => {
                                const updated = s.simulated_configs.map(c => c.id === sc.id ? { ...c, override_max_cashout: e.target.value } : c)
                                setSettings({ ...s, simulated_configs: updated })
                              }} />
                          </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div>
                            <label className="block text-xs font-medium text-slate-400 mb-1.5">Grant Test Balance</label>
                            <Input type="text" value={sc.grant_test_balance}
                              onBlur={e => updateSimConfig(sc.id, { grant_test_balance: e.target.value })}
                              onChange={e => {
                                const updated = s.simulated_configs.map(c => c.id === sc.id ? { ...c, grant_test_balance: e.target.value } : c)
                                setSettings({ ...s, simulated_configs: updated })
                              }} />
                            <p className="text-xs text-muted mt-1">Auto-grant balance on session start (0 = disabled)</p>
                          </div>
                          <div className="flex items-center gap-3 pt-6">
                            <button
                              onClick={() => updateSimConfig(sc.id, { apply_to_all_players: !sc.apply_to_all_players })}
                              className={`relative w-11 h-6 rounded-full transition-colors cursor-pointer ${
                                sc.apply_to_all_players ? 'bg-primary' : 'bg-surface-hover'
                              }`}
                            >
                              <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                                sc.apply_to_all_players ? 'translate-x-5' : ''
                              }`} />
                            </button>
                            <span className="text-sm text-slate-300">Apply to all players</span>
                          </div>
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">Notes</label>
                          <textarea value={sc.notes} rows={2} placeholder="Internal notes about this test..."
                            className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-white resize-none"
                            onBlur={e => updateSimConfig(sc.id, { notes: e.target.value })}
                            onChange={e => {
                              const updated = s.simulated_configs.map(c => c.id === sc.id ? { ...c, notes: e.target.value } : c)
                              setSettings({ ...s, simulated_configs: updated })
                            }} />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </>
        )}

        {/* Save / Cancel Buttons (for auth & game tabs) */}
        {tab !== 'simulated' && (
          <div className="flex items-center justify-end gap-3">
            {saved && <span className="text-sm text-success flex items-center gap-1"><Check size={16} /> Saved successfully</span>}
            <Button variant="ghost" onClick={() => { setLoading(true); refresh() }} disabled={saving} size="lg">
              Cancel
            </Button>
            <Button onClick={saveSettings} disabled={saving} size="lg">
              <Save size={18} />
              {saving ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        )}
      </div>
    </>
  )
}
