<script setup>
// 当日树脂加总台：只读数，不提供任何改态 / 改树脂入口。
// 每次进入本页（onMounted）都向后端实时聚合，面板新登一笔后再打开本页，
// 条数与合计必须与晾晒架下方流水里今天的记录对得上。
import { computed, onMounted, ref } from 'vue'
import api from '../api'

const data = ref(null)
const error = ref('')

const groups = computed(() => {
  if (!data.value) return []
  const map = new Map()
  for (const row of data.value.items) {
    const key = row.loftName || '未分间'
    if (!map.has(key)) map.set(key, { loftName: key, rows: [], resin: 0 })
    const g = map.get(key)
    g.rows.push(row)
    g.resin += Number(row.resinPct)
  }
  return [...map.values()]
})

async function load() {
  error.value = ''
  try {
    const res = await api.get('/resin-totals/today/')
    data.value = res.data
  } catch {
    error.value = '加总台加载失败'
  }
}

onMounted(load)
</script>

<template>
  <div class="total-page">
    <header class="rack-head">
      <div>
        <h1>当日树脂加总台</h1>
        <p class="sub">
          只读台页：汇总今日新登记浸渍的条数与树脂百分比合计，数据与晾晒架下方流水逐条一致。
          本页不改态、不改树脂。
        </p>
      </div>
      <button class="btn secondary" type="button" @click="load">刷新加总</button>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <template v-if="data">
      <div class="cards">
        <div class="card">
          <p class="label">日期（{{ data.timezone }}）</p>
          <p class="value" style="font-size:1.35rem">{{ data.date }}</p>
        </div>
        <div class="card">
          <p class="label">今日新登记浸渍条数</p>
          <p class="value">{{ data.count }}</p>
        </div>
        <div class="card">
          <p class="label">树脂百分比合计</p>
          <p class="value">{{ data.resinPctTotal }}%</p>
        </div>
      </div>

      <section v-for="g in groups" :key="g.loftName" class="panel">
        <div class="total-group-head">
          <strong>{{ g.loftName }}</strong>
          <span class="hint">{{ g.rows.length }} 条 · 合计 {{ g.resin.toFixed(2) }}%</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>布卷</th>
              <th>开始时间</th>
              <th>树脂 %</th>
              <th>固化时长 h</th>
              <th>备注</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in g.rows" :key="row.id">
              <td>{{ row.rollCode }}</td>
              <td>{{ new Date(row.startedAt).toLocaleString() }}</td>
              <td>{{ row.resinPct }}</td>
              <td>{{ row.cureHours ?? '—' }}</td>
              <td>{{ row.notes }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <p v-if="!data.items.length" class="hint">今日尚无浸渍登记。</p>
    </template>
  </div>
</template>
