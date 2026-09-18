import request from '@/utils/request';
import type {
  WebhookAddress,
  WebhookAddressLimited,
  WebhookAddressFormData,
  MessageTemplate,
  MessageTemplateFormData,
  PaginatedResponse,
} from '../types';

export type {
  WebhookAddress,
  WebhookAddressLimited,
  WebhookAddressFormData,
  MessageTemplate,
  MessageTemplateFormData,
  PaginatedResponse,
} from '../types';

const BASE_URL = '/notifications';

// ==================== Webhook 地址管理 ====================

export async function getWebhookAddresses(): Promise<WebhookAddress[] | WebhookAddressLimited[]> {
  const response = await request.get(`${BASE_URL}/webhook-addresses/`);
  const data = response.data?.data || response.data;
  if (Array.isArray(data)) return data;
  return data?.results || [];
}

export async function createWebhookAddress(data: WebhookAddressFormData): Promise<WebhookAddress> {
  const response = await request.post(`${BASE_URL}/webhook-addresses/`, data);
  return response.data?.data || response.data;
}

export async function updateWebhookAddress(id: number, data: Partial<WebhookAddressFormData>): Promise<WebhookAddress> {
  const response = await request.patch(`${BASE_URL}/webhook-addresses/${id}/`, data);
  return response.data?.data || response.data;
}

export async function deleteWebhookAddress(id: number): Promise<void> {
  await request.delete(`${BASE_URL}/webhook-addresses/${id}/`);
}

export async function testWebhookAddress(id: number): Promise<{ message: string }> {
  const response = await request.post(`${BASE_URL}/webhook-addresses/${id}/test/`);
  return response.data?.data || response.data;
}

// ==================== 消息模板管理 ====================

export async function getMessageTemplates(): Promise<MessageTemplate[]> {
  const response = await request.get(`${BASE_URL}/message-templates/`);
  const data = response.data?.data || response.data;
  if (Array.isArray(data)) return data;
  return data?.results || [];
}

export async function createMessageTemplate(data: MessageTemplateFormData): Promise<MessageTemplate> {
  const response = await request.post(`${BASE_URL}/message-templates/`, data);
  return response.data?.data || response.data;
}

export async function updateMessageTemplate(id: number, data: Partial<MessageTemplateFormData>): Promise<MessageTemplate> {
  const response = await request.patch(`${BASE_URL}/message-templates/${id}/`, data);
  return response.data?.data || response.data;
}

export async function deleteMessageTemplate(id: number): Promise<void> {
  await request.delete(`${BASE_URL}/message-templates/${id}/`);
}
