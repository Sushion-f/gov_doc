import { ApiResponse, DataSource } from '@/types';
import request from './request';

export function getDataSourceList(): Promise<ApiResponse<DataSource[]>> {
  return request({
    url: '/police/brain/datasource/list',
    method: 'get',
  });
}

export function addDataSource(data: {
  name: string;
  type: string;
  host: string;
  port: number;
  username: string;
  password: string;
  databaseName: string;
}): Promise<ApiResponse<{
  id: string;
  name: string;
  type: string;
  host: string;
  tables: number;
  records: number;
  status: string;
  lastSync: string;
}>> {
  return request({
    url: '/police/brain/datasource/add',
    method: 'post',
    data,
  });
}

export function testDataSource(data: {
  name: string;
  type: string;
  host: string;
  port: number;
  username: string;
  password: string;
  databaseName: string;
}): Promise<ApiResponse<{
  connected: boolean;
  message: string;
}>> {
  return request({
    url: '/police/brain/datasource/test',
    method: 'post',
    data,
  });
}
