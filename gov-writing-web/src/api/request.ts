import axios from 'axios';

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

request.interceptors.response.use(
  (response) => {
    const { data } = response;
    // 检查响应格式是否正确
    if (data && typeof data === 'object' && 'code' in data) {
      if (data.code === 200) {
        return data;
      }
      return Promise.reject(new Error(data.message || '请求失败'));
    }
    // 如果响应格式不符合预期，直接返回响应数据
    return data;
  },
  (error) => {
    const message = error.response?.data?.message || error.message || '网络错误';
    return Promise.reject(new Error(message));
  }
);

export default request;