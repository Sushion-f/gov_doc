import { ApiResponse, DocumentTemplate } from '@/types';
import request from './request';

export function getDocumentTemplates(): Promise<ApiResponse<{ list: DocumentTemplate[] }>> {
  return request({
    url: '/police/brain/document/templates',
    method: 'get',
  });
}
