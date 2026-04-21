import { ApiResponse, Claw } from '@/types';
import request from './request';

export function getClawList(): Promise<ApiResponse<Claw[]>> {
  return request({
    url: '/police/brain/claw/list',
    method: 'get',
  });
}

export function getClawDetail(clawId: string): Promise<ApiResponse<Claw>> {
  return request({
    url: `/police/brain/claw/detail/${clawId}`,
    method: 'get',
  });
}
