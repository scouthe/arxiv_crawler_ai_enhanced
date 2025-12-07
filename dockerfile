# 1. 【修改点】使用 DaoCloud 镜像源代替官方源 (绕过 Docker Hub 封锁)
FROM docker.m.daocloud.io/python:3.11-slim

# 2. 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 3. 设置工作目录
WORKDIR /app

RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*
    
# 4. 【修改点】配置 pip 为清华源 (加速依赖安装，否则下一步还会卡住)
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 5. 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. 复制代码
COPY . .

# 7. 启动服务
EXPOSE 8000
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]