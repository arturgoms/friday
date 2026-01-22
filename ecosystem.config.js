module.exports = {
  apps: [
    {
      name: 'friday-telegram',
      script: '.venv/bin/python',
      args: 'src/interfaces/telegram/run.py',
      cwd: '/srv/friday',
      env: {
        TZ: 'America/Sao_Paulo',
        PATHS_ROOT: '/srv/friday',
        PATHS_DATA: '/srv/friday/data',
        PATHS_LOGS: '/srv/friday/logs',
      },
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      error_file: '/srv/friday/logs/friday-telegram-error.log',
      out_file: '/srv/friday/logs/friday-telegram.log',
      merge_logs: true,
      autorestart: true,
      max_restarts: 10,
      restart_delay: 5000,
    },
    {
      name: 'friday-awareness',
      script: '.venv/bin/python',
      args: 'src/awareness/engine.py',
      cwd: '/srv/friday',
      env: {
        TZ: 'America/Sao_Paulo',
        PATHS_ROOT: '/srv/friday',
        PATHS_DATA: '/srv/friday/data',
        PATHS_LOGS: '/srv/friday/logs',
      },
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      error_file: '/srv/friday/logs/friday-awareness-error.log',
      out_file: '/srv/friday/logs/friday-awareness.log',
      merge_logs: true,
      autorestart: true,
      max_restarts: 10,
      restart_delay: 5000,
    }
  ]
};
