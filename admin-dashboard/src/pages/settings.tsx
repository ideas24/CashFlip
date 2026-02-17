import { useEffect, useState } from 'react'
import { Topbar } from '@/components/layout/topbar'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'
import { Settings, Save, Shield, Gamepad2, Megaphone, Gift } from 'lucide-react'

interface AuthSettings {
  sms_otp_enabled: boolean
  whatsapp_otp_enabled: boolean
  google_enabled: boolean
  facebook_enabled: boolean
  otp_expiry_minutes: number
  max_otp_per_hour: number
}

interface GameSettings {
  house_edge_percent: string
  min_stake: string
  max_stake: string
  zero_base_rate: string
  max_multiplier: string
}

interface AllSettings {
  auth: AuthSettings
  game: GameSettings
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<AllSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [tab, setTab] = useState<'auth' | 'game'>('auth')

  useEffect(() => {
    api.get<AllSettings>('/settings/')
      .then(setSettings)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const saveSettings = async () => {
    if (!settings) return
    setSaving(true)
    try {
      await api.post('/settings/', settings)
    } catch {}
    setSaving(false)
  }

  const updateAuth = (key: keyof AuthSettings, value: boolean | number) => {
    if (!settings) return
    setSettings({ ...settings, auth: { ...settings.auth, [key]: value } })
  }

  const updateGame = (key: keyof GameSettings, value: string) => {
    if (!settings) return
    setSettings({ ...settings, game: { ...settings.game, [key]: value } })
  }

  if (loading) {
    return (
      <>
        <Topbar title="Settings" />
        <div className="p-6"><div className="h-64 rounded-xl border border-border bg-card animate-pulse" /></div>
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
                  <Input
                    type="number"
                    value={s.auth.otp_expiry_minutes}
                    onChange={e => updateAuth('otp_expiry_minutes', parseInt(e.target.value) || 5)}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">Max OTP per hour</label>
                  <Input
                    type="number"
                    value={s.auth.max_otp_per_hour}
                    onChange={e => updateAuth('max_otp_per_hour', parseInt(e.target.value) || 6)}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {tab === 'game' && (
          <Card>
            <CardHeader>
              <CardTitle>Game Configuration</CardTitle>
              <CardDescription>Core game engine parameters</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {([
                  { key: 'house_edge_percent' as const, label: 'House Edge (%)', placeholder: '60.00' },
                  { key: 'min_stake' as const, label: 'Min Stake (GHS)', placeholder: '1.00' },
                  { key: 'max_stake' as const, label: 'Max Stake (GHS)', placeholder: '1000.00' },
                  { key: 'zero_base_rate' as const, label: 'Zero Base Rate', placeholder: '0.05' },
                  { key: 'max_multiplier' as const, label: 'Max Multiplier', placeholder: '100' },
                ]).map(item => (
                  <div key={item.key}>
                    <label className="block text-sm font-medium text-slate-300 mb-1.5">{item.label}</label>
                    <Input
                      type="text"
                      value={s.game[item.key]}
                      onChange={e => updateGame(item.key, e.target.value)}
                      placeholder={item.placeholder}
                    />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        <div className="flex justify-end">
          <Button onClick={saveSettings} disabled={saving} size="lg">
            <Save size={18} />
            {saving ? 'Saving...' : 'Save Changes'}
          </Button>
        </div>
      </div>
    </>
  )
}
