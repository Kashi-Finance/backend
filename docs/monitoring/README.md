# Cloud Monitoring Configuration

> **Pre-Production Checklist Item:** Configure these alerts in Google Cloud Monitoring before production deployment.

**Last Updated:** November 30, 2025

---

## Overview

This document defines the monitoring alerts that must be configured in Google Cloud Monitoring for the Kashi Finances backend service.

---

## Required Alerts

### High Priority (Production Blockers)

| Alert | Condition | Threshold | Window | Notification |
|-------|-----------|-----------|--------|--------------|
| **API Latency** | P95 response time | > 2 seconds | 5 min | PagerDuty + Email |
| **Error Rate** | 5xx responses / total requests | > 5% | 5 min | PagerDuty + Email |
| **DB Connection Pool** | Available connections | = 0 | 1 min | PagerDuty |

### Medium Priority

| Alert | Condition | Threshold | Window | Notification |
|-------|-----------|-----------|--------|--------------|
| **Memory Usage** | Container memory utilization | > 80% | 10 min | Email |
| **Invoice OCR Failures** | OCR errors / total OCR requests | > 10% | 30 min | Email |
| **CPU Throttling** | CPU throttled time | > 25% | 5 min | Email |

### Low Priority

| Alert | Condition | Threshold | Window | Notification |
|-------|-----------|-----------|--------|--------------|
| **Recurring Sync Failures** | Sync RPC errors | Any | 1 hour | Slack |
| **Cold Starts** | Container instance restarts | > 3 | 15 min | Slack |

---

## Setup Instructions

### 1. Cloud Run Metrics (Automatic)

Cloud Run automatically exports these metrics to Cloud Monitoring:
- `run.googleapis.com/request_latencies` - Request latency distribution
- `run.googleapis.com/request_count` - Request count by response code
- `run.googleapis.com/container/memory/utilization` - Memory usage
- `run.googleapis.com/container/cpu/utilization` - CPU usage

### 2. Custom Metrics (To Implement)

For business-level metrics, add custom logging with structured data:

```python
# Example: Invoice OCR metrics
logger.info(
    "invoice_ocr_result",
    extra={
        "metric_type": "invoice_ocr",
        "success": True,
        "latency_ms": 1234,
        "user_id": user_id,  # Hashed or anonymized
    }
)
```

Then create log-based metrics in Cloud Logging:
1. Navigate to Cloud Logging > Logs-based Metrics
2. Create counter metric for `jsonPayload.metric_type="invoice_ocr"`
3. Use labels: `success`, `latency_bucket`

### 3. Alert Policy Configuration

Example Terraform for API latency alert:

```hcl
resource "google_monitoring_alert_policy" "api_latency" {
  display_name = "Kashi API Latency > 2s"
  combiner     = "OR"
  
  conditions {
    display_name = "P95 Latency > 2000ms"
    
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_latencies\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 2000
      
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_PERCENTILE_95"
      }
    }
  }
  
  notification_channels = [google_monitoring_notification_channel.pagerduty.id]
}
```

---

## Dashboard Recommendations

Create a Cloud Monitoring dashboard with:

1. **Request Overview**
   - Request count (stacked by status code)
   - P50/P95/P99 latency
   - Error rate %

2. **Resource Utilization**
   - Memory utilization
   - CPU utilization
   - Instance count

3. **Business Metrics**
   - Invoice OCR success rate
   - Recommendation query volume
   - Active users (from auth logs)

---

## Runbook Links

| Alert | Runbook |
|-------|---------|
| API Latency | Check slow queries, scale instances |
| Error Rate | Check logs, recent deployments |
| DB Pool Exhaustion | Check connection leaks, increase pool size |
| Memory Usage | Check for leaks, tune container resources |

---

## Environment Variables

Required for Cloud Run deployment:

| Variable | Description |
|----------|-------------|
| `ENVIRONMENT` | `production` for production alerts |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID for metrics |

---

## Verification Checklist

Before production:

- [ ] All high-priority alerts configured
- [ ] PagerDuty integration tested
- [ ] Email notification channel verified
- [ ] Dashboard created and accessible
- [ ] Alert policies tested with synthetic failures
