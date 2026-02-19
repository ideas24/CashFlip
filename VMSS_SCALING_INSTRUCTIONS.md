# VMSS Scaling Instructions for CashFlip Production

## Overview

CashFlip runs on two Azure VM Scale Sets (VMSS):
- `cashflip-app-vmss`: Django app + Nginx
- `cashflip-celery-vmss`: Celery workers

You can scale these using the updated `deploy-prod.sh` script.

---

## Using the Deploy Script

### Scale App VMSS Only

```bash
# Scale app to 4 instances (celery unchanged)
./scripts/deploy-prod.sh --scale 4
```

### Scale Both App and Celery

```bash
# Scale app to 4 instances, celery to 2 instances
./scripts/deploy-prod.sh --scale 4 2
```

### Scale Celery Only

```bash
# Scale celery to 3 instances (app unchanged)
./scripts/deploy-prod.sh --scale 0 3
```

**What happens:**
1. Azure VMSS is scaled to the new capacity
2. New instances are provisioned automatically
3. Code is deployed to all instances (including new ones)
4. Services are restarted

---

## Manual Scaling via Azure CLI

If you prefer manual control:

```bash
# Set resource group (adjust if different)
RG=cashflip-prod-rg

# Scale app VMSS
az vmss scale \
  --resource-group $RG \
  --name cashflip-app-vmss \
  --new-capacity 4

# Scale celery VMSS
az vmss scale \
  --resource-group $RG \
  --name cashflip-celery-vmss \
  --new-capacity 2
```

---

## Scaling Considerations

### When to Scale Up

- **High CPU/Memory**: Monitor via Azure Monitor or `./scripts/deploy-prod.sh --status`
- **Slow Response Times**: Check Nginx logs and Django request latency
- **Queue Buildup**: Long Celery task queues indicate need for more workers
- **Traffic Spikes**: Promotions, peak hours, marketing campaigns

### When to Scale Down

- **Low Utilization**: Sustained low CPU/memory during off-peak hours
- **Cost Optimization**: Reduce instances during night hours if traffic permits

### Recommended Scaling Ranges

| Component | Min | Max | Typical |
|-----------|-----|-----|---------|
| App VMSS  | 2   | 8   | 2–4     |
| Celery VMSS | 1   | 4   | 1–2     |

---

## Health Checks & Monitoring

After scaling, verify health:

```bash
# Check service status on all VMs
./scripts/deploy-prod.sh --status

# View recent logs
./scripts/deploy-prod.sh --logs

# View journal for specific service
./scripts/deploy-prod.sh --journal cashflip 50
```

Look for:
- All instances show `active` for services
- No errors in logs during scaling
- Load balancer distributing traffic

---

## Auto Scaling (Future Enhancement)

For production, consider Azure Auto Scale rules:

```bash
# Example: Scale based on CPU percentage
az monitor autoscale create \
  --resource-group $RG \
  --resource cashflip-app-vmss \
  --min-count 2 \
  --max-count 6 \
  --count 2

az monitor autoscale rule create \
  --resource-group $RG \
  --resource-name cashflip-app-vmss \
  --autoscale-name cashflip-app-autoscale \
  --condition "Percentage CPU > 70 average 5 minutes" \
  --scale out 1

az monitor autoscale rule create \
  --resource-group $RG \
  --resource-name cashflip-app-vmss \
  --autoscale-name cashflip-app-autoscale \
  --condition "Percentage CPU < 30 average 10 minutes" \
  --scale in 1
```

---

## Troubleshooting

### Instances Not Ready After Scaling

1. Check VMSS provisioning state:
   ```bash
   az vmss show --resource-group $RG --name cashflip-app-vmss --query "provisioningState"
   ```

2. View instance status:
   ```bash
   az vmss list-instances --resource-group $RG --name cashflip-app-vmss --output table
   ```

3. Re-run deploy if instances failed to update:
   ```bash
   ./scripts/deploy-prod.sh
   ```

### Service Failures on New Instances

- Check logs: `./scripts/deploy-prod.sh --journal cashflip 100`
- Ensure `.env` file was pushed (use `--with-env` if needed)
- Verify dependencies installed correctly

### Load Balancer Issues

- Allow 2–3 minutes for health probes to detect new instances
- Check backend pool configuration in Azure portal

---

## Cost Impact

- **App VMSS**: Each instance ~B2s (2 vCPU, 4GB RAM) ≈ $0.05/hour
- **Celery VMSS**: Each instance ~B1s (1 vCPU, 1GB RAM) ≈ $0.025/hour

Example monthly costs (USD):
- 2 app + 1 celery: ~$78
- 4 app + 2 celery: ~$156

Monitor via Azure Cost Management to optimize.

---

## Emergency Scaling

For sudden traffic spikes:

```bash
# Quick scale to max recommended
./scripts/deploy-prod.sh --scale 8 4

# Monitor and scale back down after spike
./scripts/deploy-prod.sh --scale 2 1
```

---

Need help? Check Azure VMSS documentation or run `./scripts/deploy-prod.sh --help`.
