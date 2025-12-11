<template>
  <a-modal
    v-model:visible="internalVisible"
    title="执行测试用例"
    :width="480"
    @ok="handleConfirm"
    @cancel="handleCancel"
    ok-text="开始执行"
    cancel-text="取消"
  >
    <div class="execute-modal-content">
      <a-descriptions :column="1" bordered size="small" class="testcase-info">
        <a-descriptions-item label="用例名称">
          {{ testCase?.name || '-' }}
        </a-descriptions-item>
        <a-descriptions-item label="用例等级">
          <a-tag :color="getLevelColor(testCase?.level)">
            {{ testCase?.level || '-' }}
          </a-tag>
        </a-descriptions-item>
      </a-descriptions>

      <a-divider orientation="left">执行选项</a-divider>

      <a-form :model="formData" layout="vertical">
        <a-form-item>
          <a-checkbox v-model="formData.generatePlaywrightScript">
            <span class="checkbox-label">
              <icon-code class="checkbox-icon" />
              <span class="checkbox-text">
                <span class="checkbox-title">执行完成后自动生成 Playwright 脚本</span>
                <span class="checkbox-desc">开启后，AI 执行过程中的浏览器操作将被转换为可重复执行的自动化用例</span>
              </span>
            </span>
          </a-checkbox>
        </a-form-item>

        <a-form-item v-if="formData.generatePlaywrightScript">
          <template #label>
            <span>脚本格式</span>
          </template>
          <a-radio-group v-model="formData.usePytest" direction="vertical">
            <a-radio :value="true">
              <div class="radio-option">
                <span class="radio-title">Pytest 格式</span>
                <span class="radio-desc">生成标准的 pytest 测试类，适合集成到 CI/CD 流程</span>
              </div>
            </a-radio>
            <a-radio :value="false">
              <div class="radio-option">
                <span class="radio-title">简单脚本</span>
                <span class="radio-desc">生成独立的 Python 脚本，可直接运行</span>
              </div>
            </a-radio>
          </a-radio-group>
        </a-form-item>
      </a-form>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import { IconCode } from '@arco-design/web-vue/es/icon';
import type { TestCase } from '@/services/testcaseService';

interface Props {
  visible: boolean;
  testCase: TestCase | null;
}

interface Emits {
  (e: 'update:visible', value: boolean): void;
  (e: 'confirm', options: { generatePlaywrightScript: boolean; usePytest: boolean }): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const internalVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
});

const formData = ref({
  generatePlaywrightScript: false,
  usePytest: true,
});

// 重置表单
watch(
  () => props.visible,
  (val) => {
    if (val) {
      formData.value = {
        generatePlaywrightScript: false,
        usePytest: true,
      };
    }
  }
);

const getLevelColor = (level?: string) => {
  const colors: Record<string, string> = {
    P0: 'red',
    P1: 'orange',
    P2: 'blue',
    P3: 'gray',
  };
  return colors[level || ''] || 'gray';
};

const handleConfirm = () => {
  emit('confirm', {
    generatePlaywrightScript: formData.value.generatePlaywrightScript,
    usePytest: formData.value.usePytest,
  });
  internalVisible.value = false;
};

const handleCancel = () => {
  internalVisible.value = false;
};
</script>

<style scoped lang="less">
.execute-modal-content {
  .testcase-info {
    margin-bottom: 16px;
  }

  .checkbox-label {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    font-weight: 500;
  }

  .checkbox-icon {
    color: var(--color-primary-6);
    margin-top: 2px;
  }

  .checkbox-text {
    display: flex;
    flex-direction: column;
  }

  .checkbox-title {
    font-weight: 500;
  }

  .checkbox-desc {
    font-size: 12px;
    color: var(--color-text-3);
    margin-top: 4px;
    font-weight: 400;
  }

  .radio-option {
    display: flex;
    flex-direction: column;

    .radio-title {
      font-weight: 500;
    }

    .radio-desc {
      font-size: 12px;
      color: var(--color-text-3);
      margin-top: 2px;
    }
  }

  :deep(.arco-radio) {
    margin-bottom: 8px;
  }
}
</style>
