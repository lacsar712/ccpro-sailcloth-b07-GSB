<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import api from '../api'

const summary = ref(null)
const error = ref('')
const loading = ref(false)

async function load() {
  error.value = ''
  loading.value = true
  try {
    const { data } = await api.get('/dips/daily-total/')
    summary.value = data
  } catch {
    error.value = '加总台加载失败'
  } finally {
    loading.value = false
  }
}

function onFocus() {
  load()
}

onMounted(() => {
  load()
  window.addEventListener('focus', onFocus)
})

onBeforeUnmount(() => {
  window.removeEventListener('focus', onFocus)
})
</script>

<template>
  <div class="total-page">
    <header class="rack-head">
      <div>
        <h1>当日树脂加总台</h1>
        <p class="sub">
          {{ summary?.date || '今天' }} 本间新登记浸渍的条数与树脂百分比合计。本页只读：不能改态、不能改树脂。
        </p>
      </div>
      <button class="btn secondary" type="button" :disabled="loading" @click="load">
        刷新加总
      </button>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <template v-if="summary">
      <div class="cards">
        <div class="card">
          <div class="label">今日新登记浸渍（条）</div>
          <div class="value">{{ summary.totalCount }}</div>
        </div>
        <div class="card">
          <div class="label">树脂百分比合计（%）</div>
          <div class="value">{{ summary.totalResinPct }}</div>
        </div>
      </div>

      <section class="panel">
        <h2 class="feed-title">分间加总</h2>
        <table v-if="summary.lofts.length">
          <thead>
            <tr>
              <th>帆布间</th>
              <th>今日条数</th>
              <th>树脂合计 %</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in summary.lofts" :key="row.loftId">
              <td>{{ row.loftName }}</td>
              <td>{{ row.count }}</td>
              <td>{{ row.resinPctSum }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="hint" style="margin: 12px 0 0">今日尚无浸渍登记</p>
      </section>

      <section class="panel">
        <h2 class="feed-title">今日登记明细</h2>
        <p class="hint" style="margin: 0 0 12px">
          与晾晒架下方浸渍流水的今日记录一一对应，仅作核对，不可在此修改。
        </p>
        <table v-if="summary.entries.length">
          <thead>
            <tr>
              <th>布卷</th>
              <th>帆布间</th>
              <th>开始时间</th>
              <th>树脂 %</th>
              <th>固化时长 h</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in summary.entries" :key="row.id">
              <td>{{ row.rollCode }}</td>
              <td>{{ row.loftName }}</td>
              <td>{{ new Date(row.startedAt).toLocaleString() }}</td>
              <td>{{ row.resinPct }}</td>
              <td>{{ row.cureHours ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="hint" style="margin: 0">今日尚无浸渍登记</p>
      </section>
    </template>
  </div>
</template>
