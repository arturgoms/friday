# Friday AI - External Service Monitoring

## Monitored Services

1. Proxmox - https://192.168.1.15:8006
2. Portainer - https://192.168.1.16:9000
3. Immich - http://192.168.1.16:3001
4. TrueNAS - http://192.168.1.17
5. Grafana - http://192.168.1.16:8087

## Configuration

Services configured in: config/external_services.json

## Testing

Send status report:
  ./friday report

Check logs:
  ./friday logs homelab_monitor

## Adding Services

1. Edit config/external_services.json
2. Add new service entry
3. Restart: sudo systemctl restart homelab-monitor.service

## Alerts

- Service Down: Notification when unreachable
- Service Recovered: Notification when back online
- Cooldown: 5 minutes between same alerts
