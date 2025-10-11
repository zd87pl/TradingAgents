# TradingAgents + Autonomous System Test Plan

## Test Strategy

### 1. **Unit Tests** (Component Level)
Test individual components in isolation with mocked dependencies.

#### Core Components to Test:
- [ ] **Rate Limiter** (`test_rate_limiter.py`)
  - Sliding window rate limiting
  - Token bucket algorithm
  - Distributed vs local fallback
  - Rate limit exceeded handling

- [ ] **Circuit Breaker** (`test_circuit_breaker.py`)
  - State transitions (CLOSED → OPEN → HALF_OPEN)
  - Failure threshold detection
  - Timeout and recovery
  - Statistics tracking

- [ ] **Signal Deduplicator** (`test_signal_deduplicator.py`)
  - Fingerprint generation
  - Duplicate detection
  - TTL expiration
  - Redis vs local fallback

- [ ] **Risk Orchestrator** (`test_risk_orchestrator.py`)
  - Quantitative risk calculations
  - Qualitative assessment integration
  - Combined scoring logic
  - Risk violation detection

- [ ] **Perplexity AI Connector** (`test_perplexity_ai.py`)
  - API call formatting
  - Response parsing
  - Error handling
  - Rate limiting integration

### 2. **Integration Tests** (System Workflows)
Test interactions between multiple components.

#### Workflows to Test:
- [ ] **Signal Processing Pipeline** (`test_signal_pipeline.py`)
  - Data aggregation → Signal generation → Deduplication → Processing
  - Circuit breaker protection for data sources
  - Async/sync coordination

- [ ] **Trading Decision Flow** (`test_trading_flow.py`)
  - Market analysis → Risk assessment → Order generation
  - TradingAgents integration with Autonomous layer

- [ ] **Alert System** (`test_alert_system.py`)
  - Signal detection → Alert generation → Multi-channel delivery
  - Priority handling

### 3. **Performance Tests** (Optimization Validation)
Verify that optimizations actually improve performance.

#### Performance Metrics:
- [ ] **Async Performance** (`test_async_performance.py`)
  - Thread pool executor performance
  - Non-blocking event loop
  - Concurrent processing speed

- [ ] **Cache Efficiency** (`test_cache_performance.py`)
  - Hit rate improvements
  - Response time reduction
  - Memory usage

- [ ] **Rate Limiting** (`test_rate_limit_performance.py`)
  - Distributed coordination
  - Throughput under limits
  - Multi-instance scenarios

### 4. **End-to-End Tests** (Full System)
Test complete scenarios from market data to trading decisions.

#### Scenarios:
- [ ] **Market Open Routine** (`test_e2e_market_open.py`)
  - Portfolio sync → Market scan → Signal generation → Trading decisions

- [ ] **Congressional Trade Alert** (`test_e2e_congressional.py`)
  - Trade detection → Signal creation → Risk check → Alert

- [ ] **API Failure Recovery** (`test_e2e_resilience.py`)
  - Primary API fails → Circuit breaker opens → Fallback to secondary
  - System continues operating

## Test Infrastructure

### Required Test Fixtures:
1. **Mock Data Providers**
   - Market data
   - News feeds
   - Congressional trades

2. **Test Database**
   - In-memory SQLite for unit tests
   - PostgreSQL container for integration tests

3. **Mock Redis**
   - fakeredis for unit tests
   - Redis container for integration tests

4. **Mock APIs**
   - Perplexity AI responses
   - Alpha Vantage data
   - IBKR connection

## Coverage Targets

- **Unit Tests**: 80% coverage minimum
- **Integration Tests**: Critical paths covered
- **Performance Tests**: Baseline metrics established
- **E2E Tests**: Happy path + failure scenarios

## Test Execution Strategy

### Local Development:
```bash
# Fast unit tests only
pytest tests/unit -v

# Integration tests
pytest tests/integration -v

# All tests
pytest tests/ -v --cov=autonomous --cov=tradingagents
```

### CI/CD Pipeline:
1. Unit tests on every commit
2. Integration tests on PR
3. Performance tests nightly
4. E2E tests before release

## Success Criteria

1. **Functional**: All components work as designed
2. **Performance**: 3x improvement verified
3. **Reliability**: Circuit breakers prevent cascading failures
4. **Accuracy**: No duplicate signals processed
5. **Resilience**: System recovers from API failures