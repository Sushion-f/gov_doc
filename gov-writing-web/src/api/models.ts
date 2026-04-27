import request from '@/utils/request';

type ApiEnvelope<T> = {
  code: number;
  message: string;
  data: T;
};

export interface ModelItem {
  modelName: string;
  modelDisplayName: string;
}

export async function listModels(): Promise<ModelItem[]> {
  const res = (await request.get('/models')) as ApiEnvelope<ModelItem[]>;
  return Array.isArray(res.data) ? res.data : [];
}
