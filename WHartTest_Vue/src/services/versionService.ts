/**
 * 版本管理服务
 * 提供版本号显示功能
 */
import packageJson from '../../package.json'

/**
 * 获取当前版本号
 */
export function getCurrentVersion(): string {
  return packageJson.version || '0.0.0'
}

/**
 * 格式化版本号显示
 */
export function formatVersion(version: string): string {
  if (!version || version === '0.0.0') {
    return 'dev'
  }
  return `v${version.replace(/^v/, '')}`
}
