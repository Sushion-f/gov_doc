import { ApiResponse, HeartbeatTask } from '@/types';
import request from './request';

export function getHeartbeatList(): Promise<ApiResponse<{ list: HeartbeatTask[] }>> {
  return request({
    url: '/police/brain/heartbeat/list',
    method: 'get',
  });
}

export function getHeartbeatDetail(taskId: string): Promise<ApiResponse<HeartbeatTask>> {
  return request({
    url: `/police/brain/heartbeat/detail/${taskId}`,
    method: 'get',
  });
}

export function saveHeartbeatTask(data: {
  items: {
    level1: string;
    level2: string;
    level3: string;
    level4: string;
    description: string;
  }[];
}): Promise<ApiResponse<{
  id: string;
  saved: boolean;
}>> {
  return request({
    url: '/police/brain/heartbeat/save',
    method: 'post',
    data,
  });
}
