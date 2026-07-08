<template>
  <div class="app-ui-automation-layout">
    <aside class="layout-aside">
      <ModuleTree ref="moduleTreeRef" :project-id="projectId" @select="onModuleSelect" />
    </aside>
    <div class="layout-content">
      <a-tabs :key="`app-ui-tabs-${locale}`" v-model:active-key="activeTab" type="card-gutter">
        <a-tab-pane key="scripts" :title="tl('脚本管理')">
          <ScriptList ref="scriptListRef" :selected-module-id="selectedModuleId" />
        </a-tab-pane>
        <a-tab-pane key="devices" :title="tl('设备管理')">
          <DeviceList ref="deviceListRef" />
        </a-tab-pane>
        <a-tab-pane key="execution-records" :title="tl('执行记录')">
          <ExecutionRecordList ref="executionRecordListRef" />
        </a-tab-pane>
        <a-tab-pane key="batch-records" :title="tl('批量执行')">
          <BatchRecordList ref="batchRecordListRef" />
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useAppI18n } from '@/composables/useAppI18n'
import { useProjectStore } from '@/store/projectStore'
import ModuleTree from './ModuleTree.vue'
import ScriptList from './ScriptList.vue'
import DeviceList from './DeviceList.vue'
import ExecutionRecordList from './ExecutionRecordList.vue'
import BatchRecordList from './BatchRecordList.vue'

const { locale, tl } = useAppI18n()
const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id ?? null)

const activeTab = ref('scripts')
const selectedModuleId = ref<number | undefined>(undefined)

const moduleTreeRef = ref()
const scriptListRef = ref()
const deviceListRef = ref()
const executionRecordListRef = ref()
const batchRecordListRef = ref()
void [moduleTreeRef, deviceListRef, executionRecordListRef, batchRecordListRef]

// 页签切换时刷新对应数据
watch(activeTab, (newTab) => {
  switch (newTab) {
    case 'scripts':
      scriptListRef.value?.refresh?.()
      break
    case 'devices':
      deviceListRef.value?.refresh?.()
      break
    case 'execution-records':
      executionRecordListRef.value?.refresh?.()
      break
    case 'batch-records':
      batchRecordListRef.value?.refresh?.()
      break
  }
})

const onModuleSelect = (moduleId: number | undefined) => {
  selectedModuleId.value = moduleId
}
</script>

<style scoped>
.app-ui-automation-layout {
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 0;
  gap: 10px;
  overflow: hidden;
  background-color: var(--color-bg-1);
}

@media (max-width: 768px) {
  .app-ui-automation-layout {
    flex-direction: column;
  }
}

.layout-aside {
  width: 260px;
  height: 100%;
  flex-shrink: 0;
  overflow: hidden;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 4px 0 10px rgba(0, 0, 0, 0.2), 0 4px 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
}

@media (max-width: 768px) {
  .layout-aside {
    width: 100%;
    height: 280px;
  }
}

.layout-content {
  flex: 1;
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 4px 0 10px rgba(0, 0, 0, 0.2), 0 4px 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
  padding: 20px;
}

:deep(.arco-tabs) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

:deep(.arco-tabs-content) {
  flex: 1;
  overflow: auto;
}

:deep(.arco-tabs-pane) {
  height: 100%;
}
</style>
