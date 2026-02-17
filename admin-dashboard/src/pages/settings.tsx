import { useEffect, useState } from 'react'
import { Topbar } from '@/components/layout/topbar'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'
import { Save, Shield, Gamepad2, FlaskConical, Plus, Trash2, X, Check } from 'lucide-react'

interface AuthSettings {
  sms_otp_enabled: boolean
  whatsapp_otp_enabled: boolean
  google_enabled: boolean
  facebook_enabled: boolean
  otp_expiry_minutes: number
  max_otp_per_hour: number
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
  max_session_duration_minutes: number
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

interface OutcomeChoice { value: string; label: string }

interface AllSettings {
  auth: AuthSettings
  game: GameSettings
  simulated_configs: SimConfig[]
  outcome_mode_choices: OutcomeChoice[]
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<AllSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [tab, setTab] = useState<'auth' | 'game' | 'simulated'>('auth')

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
      await api.post('/settings/', { auth: settings.auth, game: settings.game })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch {}
    setSaving(false)
  }

  const updateAuth = (key: keyof AuthSettings, value: boolean | number) => {
    if (!settings) return
    setSettings({ ...settings, auth: { ...settings.auth, [key]: value } })
  }

  const updateGame = (key: string, value: string | number | boolean) => {
    if (!settings) return
    setSettings({ ...settings, game: { ...settings.game, [key]: value } })
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
            { key: 'auth' as const, label: 'Authentication', icon: Shield },
            { key: 'game' as const, label: 'Game Config', icon: Gamepad2 },
            { key: 'simulated' as const, label: 'Simulation / Testing', icon: FlaskConical },
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
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </>
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
