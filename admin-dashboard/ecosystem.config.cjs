module.exports = {
  apps: [
    {
      name: 'cashflip-admin',
      script: 'npx',
      args: 'vite preview --port 4174 --host 127.0.0.1',
      cwd: '/home/terminal_ideas/cashflip/admin-dashboard',
      env: {
        NODE_ENV: 'production',
      },
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '256M',
    },
  ],
}
