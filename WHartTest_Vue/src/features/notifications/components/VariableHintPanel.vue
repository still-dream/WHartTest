<template>
  <div class="variable-hint-panel">
    <a-collapse :default-active-key="[]">
      <a-collapse-item key="vars" header="变量参考">
        <div class="var-grid">
          <div
            v-for="v in variables"
            :key="v.name"
            class="var-item"
            @click="onVarClick(v)"
          >
            <a-tooltip :content="`点击插入 {{${v.name}}} - ${v.description}`">
              <a-tag color="arcoblue" style="cursor: pointer">
                {{ '{{' + v.name + '}}' }}
              </a-tag>
            </a-tooltip>
            <span class="var-desc">{{ v.description }}</span>
          </div>
        </div>
      </a-collapse-item>
    </a-collapse>
  </div>
</template>

<script setup lang="ts">
import { NOTIFICATION_VARIABLES, type NotificationVariable } from '../types';

const variables = NOTIFICATION_VARIABLES;

const emit = defineEmits<{
  (e: 'insert', varName: string): void;
}>();

const onVarClick = (v: NotificationVariable) => {
  emit('insert', v.name);
};
</script>

<style scoped>
.variable-hint-panel {
  margin-bottom: 8px;
}

.var-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.var-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.var-desc {
  font-size: 12px;
  color: var(--color-text-3);
}
</style>
