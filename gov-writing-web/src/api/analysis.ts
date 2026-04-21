import { AnalysisItem, ApiResponse } from '@/types';
import request from './request';

export function getAnalysisHistory(): Promise<ApiResponse<{ list: AnalysisItem[] }>> {
  return request({
    url: '/police/brain/analysis/history',
    method: 'get',
  });
}
