<template>
  <main class="app-shell">
    <aside class="control-pane">
      <header class="brand">
        <div>
          <span class="eyebrow">LifeOS Decision Simulation Agent</span>
          <h1>Future Stone</h1>
        </div>
        <span class="status-pill" :class="statusClass">{{ statusText }}</span>
      </header>

      <section class="form-section">
        <label>
          场景描述
          <textarea v-model="form.scene.description" rows="5" />
        </label>
        <label>
          具体讨论的问题
          <textarea v-model="form.question" rows="3" />
        </label>
        <div class="input-grid">
          <label>
            世界数量
            <input v-model.number="form.world_count" type="number" min="1" max="100" />
          </label>
          <label>
            模拟轮次
            <input v-model.number="form.rounds" type="number" min="1" max="20" />
          </label>
        </div>
        <label>
          Avatar
          <input v-model="avatarText" />
        </label>
        <label>
          NPC 角色
          <input v-model="npcText" />
        </label>
        <label>
          Runner
          <select v-model="form.runner">
            <option value="llm">LLM SkillRunner</option>
            <option value="piagent">PiAgent SkillRunner</option>
            <option value="replay">Replay SkillRunner</option>
          </select>
        </label>
        <button class="primary-action" :disabled="busy" @click="createAndRun">
          {{ busy ? '正在推演...' : 'Run Future Stone' }}
        </button>
        <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
      </section>

      <section v-if="recentSimulations.length" class="recent-section">
        <h2>最近结果</h2>
        <button
          v-for="item in recentSimulations.slice(0, 5)"
          :key="item.simulation_id"
          class="recent-run"
          :class="{ active: item.simulation_id === activeSimulationId }"
          @click="restoreSimulation(item.simulation_id)"
        >
          <span>{{ item.recommended_path || item.status }}</span>
          <small>{{ item.completed_steps }} / {{ item.total_steps }} · {{ item.question }}</small>
        </button>
      </section>

      <section class="steps-section">
        <h2>链路</h2>
        <ol>
          <li :class="{ active: stepIndex >= 1 }">Graph Build / 抽取场景、Avatar、NPC、问题</li>
          <li :class="{ active: stepIndex >= 2 }">Environment Setup / 生成多条时间线</li>
          <li :class="{ active: stepIndex >= 3 }">Simulation Loop / 逐轮跑 LifeOS skill</li>
          <li :class="{ active: stepIndex >= 4 }">Report / 汇总不同未来的结论</li>
          <li :class="{ active: stepIndex >= 5 }">Interaction / 点开节点追问依据</li>
        </ol>
      </section>
    </aside>

    <section class="workbench">
      <header class="workbench-header">
        <div>
          <span class="eyebrow">Simulation Canvas</span>
          <h2>{{ report?.recommended_path ? `主路径：${report.recommended_path}` : '多时间线沙盘' }}</h2>
        </div>
        <div class="metric-row">
          <span><b>{{ storyMap.nodes.length }}</b> nodes</span>
          <span><b>{{ events.length }}</b> events</span>
          <span><b>{{ decisionTraces.length }}</b> decisions</span>
        </div>
      </header>

      <section class="runtime-strip" v-if="progress.status || busy">
        <span v-if="activeSimulationId" class="runtime-wide">
          <b>Run</b>
          {{ activeSimulationId }}
        </span>
        <span class="runtime-wide">
          <b>Step</b>
          {{ currentStepText }}
        </span>
        <span>
          <b>Progress</b>
          {{ progress.completed_steps || 0 }} / {{ progress.total_steps || 0 }}
          <small v-if="progressPercent">· {{ progressPercent }}%</small>
        </span>
        <span>
          <b>World/NPC</b>
          {{ progress.generation_source || 'pending' }}
          <small v-if="progress.generation_model">· {{ progress.generation_model }}</small>
        </span>
        <span>
          <b>Skill</b>
          {{ progress.skill_runner_source || form.runner }}
          <small v-if="progress.skill_runner_model">· {{ progress.skill_runner_model }}</small>
        </span>
        <span v-if="progress.fallback_reason" class="fallback-note">
          fallback: {{ progress.fallback_reason }}
        </span>
        <span>
          <b>Elapsed</b>
          {{ elapsedLabel }}
        </span>
        <span>
          <b>Updated</b>
          {{ updatedAtLabel }}
        </span>
      </section>

      <div class="canvas-layout">
        <section class="graph-pane">
          <svg ref="graphEl" class="graph"></svg>
          <div v-if="!storyMap.nodes.length" class="empty-graph">
            输入场景后运行，Future Stone 会生成时间线、NPC、skill run 和决策节点。
          </div>
        </section>

        <aside class="detail-pane">
          <h3>Node Detail</h3>
          <template v-if="selectedNode">
            <strong>{{ selectedNode.label }}</strong>
            <span class="node-type">{{ selectedNode.type }}</span>
            <p>{{ selectedNode.detail || '暂无详情' }}</p>
            <pre>{{ JSON.stringify(selectedNode.data || {}, null, 2) }}</pre>
          </template>
          <p v-else>点击任意节点查看它在推演链路中的含义。</p>
        </aside>
      </div>

      <section class="lower-grid">
        <div class="timeline-pane">
          <header>
            <h3>执行过程</h3>
            <span>{{ progress.completed_steps || 0 }} / {{ progress.total_steps || 0 }}</span>
          </header>
          <div class="event-list">
            <article v-for="event in events.slice(0, 16)" :key="event.id" class="event-item">
              <span>{{ event.world_id }} · R{{ event.round_index }} · {{ event.npc_role }}</span>
              <p>{{ event.npc_message }}</p>
              <small>{{ event.avatar_response }}</small>
            </article>
          </div>
        </div>

        <div class="skill-pane">
          <header>
            <h3>Skill Runs</h3>
            <span>{{ skillRuns.length }}</span>
          </header>
          <div class="event-list">
            <article v-for="run in skillRuns.slice(0, 10)" :key="run.id" class="event-item">
              <span>{{ run.world_id }} · R{{ run.round_index }} · {{ run.runner }}</span>
              <p>{{ run.output_decision }}：{{ run.output_rationale }}</p>
              <small>{{ run.skill_ref }} · confidence {{ run.confidence }}</small>
            </article>
          </div>
        </div>

        <div class="report-pane">
          <header>
            <h3>Report</h3>
            <span>{{ report?.timeline_count || 0 }} timelines</span>
          </header>
          <template v-if="report">
            <p>{{ report.summary }}</p>
            <div class="distribution">
              <span v-for="(count, decision) in report.decision_distribution" :key="decision">
                {{ decision }} {{ count }}
              </span>
            </div>
            <h4>关键依据</h4>
            <ul>
              <li v-for="factor in report.decisive_factors" :key="factor">{{ factor }}</li>
            </ul>
          </template>
          <p v-else>报告会在 simulation loop 完成后生成。</p>
        </div>
      </section>
    </section>
  </main>
</template>

<script setup>
import axios from 'axios'
import * as d3 from 'd3'
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'

const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:5055'
const activeSimulationStorageKey = 'future-stone.active-simulation-id'

const form = reactive({
  scene: {
    description:
      '要不要参加黑客松？Anthony 和 Neil 希望用 48 小时验证 LifeOS 的 Future Stone demo，但需要考虑家庭、团队节奏、评委标准和是否服务 LifeOS 主线。',
  },
  question: 'Anthony 和 Neil 是否应该参加这次黑客松？',
  world_count: 12,
  rounds: 3,
  runner: 'llm',
})

const avatarText = ref('AnthonyFan.LifeOS, Neil.LifeOS')
const npcText = ref('参赛选手, 家人, 评委')
const busy = ref(false)
const progress = ref({})
const storyMap = ref({ nodes: [], edges: [] })
const events = ref([])
const skillRuns = ref([])
const decisionTraces = ref([])
const report = ref(null)
const selectedNode = ref(null)
const graphEl = ref(null)
const errorMessage = ref('')
const activeSimulationId = ref('')
const runStartedAt = ref(null)
const lastStatusAt = ref(null)
const recentSimulations = ref([])

const stepIndex = computed(() => {
  if (busy.value && progress.value.completed_steps > 0) return 3
  if (busy.value) return 2
  if (!storyMap.value.nodes.length) return 0
  if (report.value) return 5
  return 2
})

const statusText = computed(() => {
  if (busy.value) return 'running'
  return progress.value.status || 'idle'
})

const statusClass = computed(() => ({
  running: busy.value || progress.value.status === 'running',
  completed: progress.value.status === 'completed',
}))

const currentStepText = computed(() => {
  if (progress.value.current_step) return progress.value.current_step
  if (busy.value) return '等待后端返回状态'
  return 'idle'
})

const progressPercent = computed(() => {
  const total = Number(progress.value.total_steps || 0)
  if (!total) return 0
  return Math.floor((Number(progress.value.completed_steps || 0) / total) * 100)
})

const elapsedLabel = computed(() => {
  if (!runStartedAt.value) return '0s'
  const now = lastStatusAt.value || Date.now()
  return formatDuration(Math.max(0, Math.floor((now - runStartedAt.value) / 1000)))
})

const updatedAtLabel = computed(() => {
  if (!progress.value.updated_at) return 'waiting'
  return formatClock(progress.value.updated_at)
})

async function createAndRun() {
  busy.value = true
  errorMessage.value = ''
  activeSimulationId.value = ''
  runStartedAt.value = Date.now()
  lastStatusAt.value = Date.now()
  selectedNode.value = null
  progress.value = {}
  storyMap.value = { nodes: [], edges: [] }
  events.value = []
  skillRuns.value = []
  decisionTraces.value = []
  report.value = null
  try {
    const payload = {
      ...form,
      avatars: splitList(avatarText.value),
      npc_roles: splitList(npcText.value),
    }
    const created = await axios.post(`${apiBase}/api/simulations`, payload)
    const simulationId = created.data.data.simulation_id
    activeSimulationId.value = simulationId
    persistActiveSimulation(simulationId)
    const started = await axios.post(`${apiBase}/api/simulations/${simulationId}/start`)
    applySimulationPayload(started.data.data)
    await loadRecentSimulations()
    if (progress.value.status !== 'completed') {
      await pollUntilCompleted(simulationId)
    }
    await loadSimulationArtifacts(simulationId)
    await loadRecentSimulations()
  } catch (error) {
    errorMessage.value = error?.response?.data?.error || error?.message || '推演失败'
  } finally {
    busy.value = false
  }
}

function applySimulationPayload(data) {
  progress.value = data.progress || {}
  if (data.story_map) storyMap.value = data.story_map
  if (data.report) report.value = data.report
}

async function loadRecentSimulations() {
  const response = await axios.get(`${apiBase}/api/simulations?limit=8`)
  recentSimulations.value = response.data.data.simulations || []
}

async function restoreSimulation(simulationId) {
  if (!simulationId) return
  busy.value = true
  errorMessage.value = ''
  activeSimulationId.value = simulationId
  persistActiveSimulation(simulationId)
  runStartedAt.value = Date.now()
  lastStatusAt.value = Date.now()
  try {
    const statusRes = await axios.get(`${apiBase}/api/simulations/${simulationId}/status`)
    progress.value = statusRes.data.data
    await loadPartialArtifacts(simulationId)
    if (progress.value.status === 'completed') {
      await loadSimulationArtifacts(simulationId)
      return
    }
    if (progress.value.status === 'running') {
      await pollUntilCompleted(simulationId)
      await loadSimulationArtifacts(simulationId)
      return
    }
    errorMessage.value = progress.value.current_step || `无法恢复 ${simulationId}`
  } catch (error) {
    errorMessage.value = error?.response?.data?.error || error?.message || '恢复结果失败'
  } finally {
    busy.value = false
    await loadRecentSimulations()
  }
}

async function pollUntilCompleted(simulationId) {
  for (let attempt = 0; attempt < 240; attempt += 1) {
    await delay(1500)
    const statusRes = await axios.get(`${apiBase}/api/simulations/${simulationId}/status`)
    lastStatusAt.value = Date.now()
    progress.value = statusRes.data.data
    await loadPartialArtifacts(simulationId)
    if (progress.value.status === 'completed') return
    if (progress.value.status === 'failed') {
      throw new Error(progress.value.current_step || '推演失败')
    }
  }
  throw new Error('推演超时')
}

async function loadSimulationArtifacts(simulationId) {
  const [storyRes, reportRes, eventsRes, skillsRes, tracesRes] = await Promise.all([
    axios.get(`${apiBase}/api/simulations/${simulationId}/story-map`),
    axios.get(`${apiBase}/api/simulations/${simulationId}/report`),
    axios.get(`${apiBase}/api/simulations/${simulationId}/events`),
    axios.get(`${apiBase}/api/simulations/${simulationId}/skill-runs`),
    axios.get(`${apiBase}/api/simulations/${simulationId}/decision-traces`),
  ])
  storyMap.value = storyRes.data.data
  report.value = reportRes.data.data
  events.value = eventsRes.data.data.events
  skillRuns.value = skillsRes.data.data.skill_runs
  decisionTraces.value = tracesRes.data.data.decision_traces
  await nextTick()
  renderGraph()
}

async function loadPartialArtifacts(simulationId) {
  const [eventsRes, skillsRes, tracesRes] = await Promise.allSettled([
    axios.get(`${apiBase}/api/simulations/${simulationId}/events`),
    axios.get(`${apiBase}/api/simulations/${simulationId}/skill-runs`),
    axios.get(`${apiBase}/api/simulations/${simulationId}/decision-traces`),
  ])
  if (eventsRes.status === 'fulfilled') events.value = eventsRes.value.data.data.events
  if (skillsRes.status === 'fulfilled') skillRuns.value = skillsRes.value.data.data.skill_runs
  if (tracesRes.status === 'fulfilled') {
    decisionTraces.value = tracesRes.value.data.data.decision_traces
  }
}

function delay(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

function formatDuration(seconds) {
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return `${minutes}m ${rest}s`
}

function formatClock(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleTimeString()
}

function persistActiveSimulation(simulationId) {
  window.localStorage.setItem(activeSimulationStorageKey, simulationId)
}

async function restoreInitialSimulation() {
  try {
    await loadRecentSimulations()
    const storedSimulationId = window.localStorage.getItem(activeSimulationStorageKey)
    const storedExists = recentSimulations.value.some(
      (item) => item.simulation_id === storedSimulationId,
    )
    const fallbackSimulationId = recentSimulations.value[0]?.simulation_id || ''
    const simulationId = storedExists ? storedSimulationId : fallbackSimulationId
    if (simulationId) await restoreSimulation(simulationId)
  } catch (error) {
    errorMessage.value = error?.message || '加载最近结果失败'
  }
}

function splitList(value) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function renderGraph() {
  if (!graphEl.value || !storyMap.value.nodes.length) return
  const svg = d3.select(graphEl.value)
  svg.selectAll('*').remove()

  const width = graphEl.value.clientWidth || 900
  const height = graphEl.value.clientHeight || 560
  const color = d3
    .scaleOrdinal()
    .domain(['question', 'scene', 'avatar', 'self_lens', 'npc_role', 'world', 'npc', 'decision'])
    .range(['#3157d5', '#65758b', '#149c88', '#8b5cf6', '#c47a14', '#0f766e', '#c2410c', '#be185d'])

  const nodes = storyMap.value.nodes.map((node) => ({ ...node }))
  const links = storyMap.value.edges.map((edge) => ({ ...edge }))
  const simulation = d3
    .forceSimulation(nodes)
    .force(
      'link',
      d3
        .forceLink(links)
        .id((node) => node.id)
        .distance((link) => (link.label === 'branches' ? 140 : 90)),
    )
    .force('charge', d3.forceManyBody().strength(-480))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide().radius(38))

  const root = svg.attr('viewBox', `0 0 ${width} ${height}`).append('g')
  const zoom = d3.zoom().scaleExtent([0.35, 2.8]).on('zoom', (event) => root.attr('transform', event.transform))
  svg.call(zoom)

  const link = root
    .append('g')
    .attr('class', 'links')
    .selectAll('line')
    .data(links)
    .enter()
    .append('line')
    .attr('stroke', '#c9d3e0')
    .attr('stroke-width', (edge) => Math.max(1, edge.weight || 1))

  const node = root
    .append('g')
    .attr('class', 'nodes')
    .selectAll('g')
    .data(nodes)
    .enter()
    .append('g')
    .attr('class', 'node')
    .call(d3.drag().on('start', dragStarted).on('drag', dragged).on('end', dragEnded))
    .on('click', (_, datum) => {
      selectedNode.value = datum
    })

  node
    .append('circle')
    .attr('r', (datum) => (datum.type === 'question' ? 22 : datum.type === 'world' ? 18 : 13))
    .attr('fill', (datum) => color(datum.type))
    .attr('stroke', '#ffffff')
    .attr('stroke-width', 2)

  node
    .append('text')
    .text((datum) => datum.label)
    .attr('x', 16)
    .attr('y', 4)
    .attr('font-size', 12)
    .attr('fill', '#172033')

  simulation.on('tick', () => {
    link
      .attr('x1', (datum) => datum.source.x)
      .attr('y1', (datum) => datum.source.y)
      .attr('x2', (datum) => datum.target.x)
      .attr('y2', (datum) => datum.target.y)
    node.attr('transform', (datum) => `translate(${datum.x},${datum.y})`)
  })

  function dragStarted(event, datum) {
    if (!event.active) simulation.alphaTarget(0.3).restart()
    datum.fx = datum.x
    datum.fy = datum.y
  }

  function dragged(event, datum) {
    datum.fx = event.x
    datum.fy = event.y
  }

  function dragEnded(event, datum) {
    if (!event.active) simulation.alphaTarget(0)
    datum.fx = null
    datum.fy = null
  }
}

watch(storyMap, () => nextTick(renderGraph), { deep: true })
onMounted(restoreInitialSimulation)
</script>
