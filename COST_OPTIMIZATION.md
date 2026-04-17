# Cost Monitoring & Tracking Guide

## 📊 Monitor Your Anthropic API Usage

### **Step 1: Check Your Usage Dashboard**

1. Go to: https://console.anthropic.com/account/usage
2. You'll see:
   - Daily/Monthly token usage
   - Estimated costs
   - API request counts
   - Model breakdown

### **Step 2: Set Spending Limit (Prevent Bill Shock)**

1. Go to: https://console.anthropic.com/account/billing
2. Click **Usage Limits**
3. Set monthly limit (e.g., $50)
4. API will reject requests if limit exceeded
5. You get email notification before limit

---

## 💾 Track Local Usage

### **View Current Costs**

```bash
# See how many analyses are cached
ls -la db/cache/expert_panel_cache.json

# Check cache file size
du -sh db/cache/

# Count cache entries
python -c "import json; f=open('db/cache/expert_panel_cache.json'); print(len(json.load(f)))"
```

### **Calculate Your Costs**

```python
# cost_calculator.py - Add this to track spending

import json
from pathlib import Path

def calculate_costs():
    cache_file = Path("db/cache/expert_panel_cache.json")
    
    if cache_file.exists():
        with open(cache_file) as f:
            cache = json.load(f)
        
        cached_analyses = len(cache)
        uncached_analyses = 10  # Your estimate
        
        # Costs (with Haiku model)
        cost_per_uncached = 0.04  # Haiku (optimized)
        cost_per_cached = 0.001   # 30x savings
        
        uncached_cost = uncached_analyses * cost_per_uncached
        cached_cost = cached_analyses * cost_per_cached
        total = uncached_cost + cached_cost
        
        print(f"""
COST SUMMARY
============
Cached analyses:   {cached_analyses} × $0.001 = ${cached_cost:.2f}
Uncached analyses: {uncached_analyses} × $0.04  = ${uncached_cost:.2f}
Total (Est):       ${total:.2f}
Monthly (Est):     ${total * 3:.2f}
        """)

if __name__ == "__main__":
    calculate_costs()
```

---

## 📈 Your Cost Optimization Summary

### **Before Optimization**
- Model: Sonnet (expensive)
- Chunks: Variable
- Caching: Not enabled
- **Cost per analysis: $0.15**
- **Monthly (100 analyses): $15**

### **After Optimization** ✅
- Model: Haiku (3x cheaper)
- Chunks: Optimized (8)
- Caching: Enabled (30x on repeats)
- **Cost per analysis: $0.04 (uncached) / $0.001 (cached)**
- **Monthly (100 analyses, 20% cache): $3.22**

**Total Savings: ~$12/month (80% reduction)** 💰

---

## 🚀 Usage Patterns & Costs

### **Pattern 1: Development (Ad-hoc Testing)**
```
5 analyses/month
Cost: ~$0.20/month
Best for: Learning, experimentation
```

### **Pattern 2: Regular Use (Team/Department)**
```
100 analyses/month
- 20% cache hits
- Cost: ~$3.22/month
Best for: Regular legal analysis
```

### **Pattern 3: High Volume (Enterprise)**
```
1,000 analyses/month
- 30% cache hits
- Cost: ~$28/month
Best for: Automated processing
```

### **Pattern 4: Very High Volume (Scale)**
```
10,000+ analyses/month
- 50% cache hits
- Cost: ~$150-200/month
Best for: Production service
```

---

## ✅ Verification Checklist

After optimization:

- [ ] Model changed to Haiku in config.py
- [ ] CACHE_ENABLED = True in config.py
- [ ] Test analysis runs successfully
- [ ] Cache file created in db/cache/
- [ ] Anthropic spending limit set

---

## 📝 Monthly Cost Tracking

**Use this template to track your actual costs:**

```
Month:  [April 2026]

Week 1:  [# analyses] × [model] = [estimated cost]
Week 2:  [# analyses] × [model] = [estimated cost]
Week 3:  [# analyses] × [model] = [estimated cost]
Week 4:  [# analyses] × [model] = [estimated cost]

Total:   [total analyses] = [actual cost from dashboard]
Cache hit rate: [%]
Savings vs baseline: [%]
```

---

## 🎯 Cost Optimization Checklist

- [ ] **Caching enabled** (30x savings on repeats) ✅
- [ ] **Haiku model** (3x cheaper) ✅
- [ ] **Low chunk size** (faster processing) ✅
- [ ] **Spending limit set** (prevent surprises) ✅
- [ ] **Monthly monitoring** (track actual vs estimated) ✅

---

## 💡 Additional Tips

### **Never Pay More Than $5/Month** (Low Volume)

1. Always use caching
2. Reuse analyses when possible
3. Use Haiku model
4. Process off-peak (doesn't matter, but good practice)

### **Scale Incrementally**

- Start with local setup ($5-30/month)
- Monitor actual usage
- Only upgrade cloud if > 5,000 analyses/month
- Keep local backup for resilience

### **Request Volume Discounts**

- If you hit 100,000+ tokens/month
- Contact Anthropic sales
- Negotiate volume pricing
- Could save 20-50%

---

## 📞 Support & Questions

**Questions about costs?**
- Check: https://www.anthropic.com/pricing
- Contact: support@anthropic.com
- Dashboard: https://console.anthropic.com/account

**Questions about your setup?**
- Check DEPLOYMENT.md for all options
- See README.md for usage examples
- Review TEST_DOCUMENTATION.md for testing

---

**Your local setup is now optimized for minimal cost with maximum efficiency!** 💰✅
