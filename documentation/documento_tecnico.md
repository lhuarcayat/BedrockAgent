# Documento Técnico

**Junio 2025**

**Para:** Par Servicios

**Versión:** 1.0

**Presentada por:** APPLYING CONSULTING S.A.C.

Av. Rivera Navarrete 515, San Isidro 15046

https://www.applying.pe

---

## Términos de Confidencialidad
Por claras razones de índole comercial, puede resultar en perjuicio de APPLYING CONSULTING S.A.C. que la información incluida en este documento sea conocida por personas distintas a aquellas a quien está dirigida.

Este documento está destinado exclusivamente para Par Servicios. Su contenido no debe ser revelado, duplicado, usado o publicado total o parcialmente, fuera de su organización, o a cualquier otra empresa, sin una autorización expresa escrita de APPLYING CONSULTING S.A.C.

Así mismo, APPLYING CONSULTING S.A.C. se compromete a no divulgar total o parcialmente el contenido de este documento referido a necesidades o requerimientos específicos para Par Servicios, así como ningún tema de negocios relacionado y que fuese mencionado en reuniones de trabajo previas.

---

## Contenido

1. [Descripción](#1-descripción)

2. [Cuentas](#2-cuentas)

   2.1. [Acceso a la cuenta](#21-acceso-a-la-cuenta)

   2.2. [Nomenclatura](#22-nomenclatura)

3. [Análisis y diseño](#3-análisis-y-diseño)

   3.1. [Arquitectura](#31-arquitectura)

4. [Infraestructura desplegada](#4-infraestructura-desplegada)

   4.1. [S3](#41-s3)

   4.2. [Lambda](#42-lambda)

   4.3. [SQS](#43-sqs)

   4.4. [Notificaciones S3](#44-notificaciones-s3)

5. [Seguridad](#5-seguridad)

   5.1. [Encriptación en reposo](#51-encriptación-en-reposo)

   5.2. [Políticas IAM](#52-políticas-iam)

---

## 1. Descripción
Este documento pretende detallar los recursos desplegados en las cuentas AWS, la arquitectura y las buenas prácticas seguidas para el procesamiento de documentos utilizando servicios serverless de AWS y Amazon Bedrock.

---

## 2. Cuentas
La cuenta AWS en la cual se realizó el presente despliegue es administrada por el cliente.
**Account ID:** 112636930635

### 2.1. Acceso a la cuenta
Para el acceso a la cuenta se utilizan usuarios IAM. El usuario principal identificado en el despliegue es "applying".

### 2.2. Nomenclatura
Para distinguir proyecto, ambiente y servicio:
- **Prefijo del proyecto:** par-servicios-poc
- **Ambientes:** dev, qa
- **Nomenclatura general:** `par-servicios-poc-[ambiente]-[recurso]`
- **Tipos de documentos:** CERL, CECRL, RUT, RUB, ACC

| Parámetro | Ambiente DEV | Ambiente QA |
|-----------|-------------|------------|
| Prefijo completo | par-servicios-poc-dev | par-servicios-poc-qa |
| Región AWS | us-east-2 (Ohio) | us-east-2 (Ohio) |
| Modelo Bedrock principal | us.amazon.nova-pro-v1:0 | us.amazon.nova-pro-v1:0 |
| Modelo Bedrock respaldo | us.anthropic.claude-sonnet-4-20250514-v1:0 | us.anthropic.claude-sonnet-4-20250514-v1:0 |

---

## 3. Análisis y diseño

### 3.1. Arquitectura
- Arquitectura serverless basada en eventos para el procesamiento de documentos.
- Flujo de trabajo:
  1. Carga de documentos en buckets S3 organizados por tipo de documento.
  2. Activación de funciones Lambda mediante eventos de creación de objetos en S3.
  3. Procesamiento de documentos utilizando modelos de Amazon Bedrock.
  4. Comunicación asíncrona entre componentes mediante colas SQS.
  5. Almacenamiento de resultados en formato JSON en un bucket S3 dedicado.

---

## 4. Infraestructura desplegada

### 4.1. S3

#### Buckets por ambiente

| Recurso | Ambiente DEV | Ambiente QA |
|---------|-------------|------------|
| **Bucket de entrada** | par-servicios-poc-dev-filling-desk | par-servicios-poc-qa-filling-desk |
| ARN | arn:aws:s3:::par-servicios-poc-dev-filling-desk | arn:aws:s3:::par-servicios-poc-qa-filling-desk |
| **Bucket de resultados** | par-servicios-poc-dev-json-evaluation-results | par-servicios-poc-qa-json-evaluation-results |
| ARN | arn:aws:s3:::par-servicios-poc-dev-json-evaluation-results | arn:aws:s3:::par-servicios-poc-qa-json-evaluation-results |

**Configuración común:**
- Versionamiento: Habilitado
- Encriptación: AES256 (SSE-S3)
- Acceso público: Bloqueado

**Estructura de carpetas en ambos ambientes:**
- par-servicios-poc/CERL/
- par-servicios-poc/CECRL/
- par-servicios-poc/RUT/
- par-servicios-poc/RUB/
- par-servicios-poc/ACC/

### 4.2. Lambda

#### Funciones Lambda por ambiente

| Función | Ambiente DEV | Ambiente QA |
|---------|-------------|------------|
| **Clasificación** | par-servicios-poc-112636930635-dev-classification | par-servicios-poc-112636930635-qa-classification |
| ARN | arn:aws:lambda:us-east-2:112636930635:function:par-servicios-poc-112636930635-dev-classification | arn:aws:lambda:us-east-2:112636930635:function:par-servicios-poc-112636930635-qa-classification |
| **Extracción y puntuación** | par-servicios-poc-112636930635-dev-extraction-scoring | par-servicios-poc-112636930635-qa-extraction-scoring |
| ARN | arn:aws:lambda:us-east-2:112636930635:function:par-servicios-poc-112636930635-dev-extraction-scoring | arn:aws:lambda:us-east-2:112636930635:function:par-servicios-poc-112636930635-qa-extraction-scoring |

**Configuración común:**
- Runtime: Python 3.12
- Handler: index.handler
- Memoria: 1024 MB
- Timeout: 900 segundos

**Variables de entorno - Clasificación:**

| Variable | Ambiente DEV | Ambiente QA |
|----------|-------------|------------|
| BEDROCK_MODEL | us.amazon.nova-pro-v1:0 | us.amazon.nova-pro-v1:0 |
| EXTRACTION_SQS | https://sqs.us-east-2.amazonaws.com/112636930635/par-servicios-poc-extraction-queue | https://sqs.us-east-2.amazonaws.com/112636930635/par-servicios-poc-qa-extraction-queue |
| FALLBACK_MODEL | us.anthropic.claude-sonnet-4-20250514-v1:0 | us.anthropic.claude-sonnet-4-20250514-v1:0 |
| REGION | us-east-2 | us-east-2 |
| S3_ORIGIN_BUCKET | par-servicios-poc-dev-filling-desk | par-servicios-poc-qa-filling-desk |

**Variables de entorno - Extracción y puntuación:**

| Variable | Ambiente DEV | Ambiente QA |
|----------|-------------|------------|
| BEDROCK_MODEL | us.amazon.nova-pro-v1:0 | us.amazon.nova-pro-v1:0 |
| DESTINATION_BUCKET | par-servicios-poc-dev-json-evaluation-results | par-servicios-poc-qa-json-evaluation-results |
| FALLBACK_MODEL | us.anthropic.claude-sonnet-4-20250514-v1:0 | us.anthropic.claude-sonnet-4-20250514-v1:0 |
| FALLBACK_SQS | https://sqs.us-east-2.amazonaws.com/112636930635/par-servicios-poc-fallback-queue | https://sqs.us-east-2.amazonaws.com/112636930635/par-servicios-poc-qa-fallback-queue |
| FOLDER_PREFIX | par-servicios-poc | par-servicios-poc |
| REGION | us-east-2 | us-east-2 |
| S3_ORIGIN_BUCKET | par-servicios-poc-dev-filling-desk | par-servicios-poc-qa-filling-desk |

### 4.3. SQS

#### Colas SQS por ambiente

| Cola | Ambiente DEV | Ambiente QA |
|------|-------------|------------|
| **Cola de extracción** | par-servicios-poc-extraction-queue | par-servicios-poc-qa-extraction-queue |
| URL | https://sqs.us-east-2.amazonaws.com/112636930635/par-servicios-poc-extraction-queue | https://sqs.us-east-2.amazonaws.com/112636930635/par-servicios-poc-qa-extraction-queue |
| ARN | arn:aws:sqs:us-east-2:112636930635:par-servicios-poc-extraction-queue | arn:aws:sqs:us-east-2:112636930635:par-servicios-poc-qa-extraction-queue |
| **Cola de respaldo** | par-servicios-poc-fallback-queue | par-servicios-poc-qa-fallback-queue |
| URL | https://sqs.us-east-2.amazonaws.com/112636930635/par-servicios-poc-fallback-queue | https://sqs.us-east-2.amazonaws.com/112636930635/par-servicios-poc-qa-fallback-queue |
| ARN | arn:aws:sqs:us-east-2:112636930635:par-servicios-poc-fallback-queue | arn:aws:sqs:us-east-2:112636930635:par-servicios-poc-qa-fallback-queue |

**Configuración común:**
- Timeout: 960 segundos
- Retención de mensajes: 345600 segundos (4 días)
- Encriptación: SSE-SQS (AES-256)

### 4.4. Notificaciones S3

#### Notificaciones por ambiente

**Ambiente DEV:**

| Evento | Prefijo | Destino |
|--------|---------|---------|
| s3:ObjectCreated:* | par-servicios-poc/CERL/ | par-servicios-poc-112636930635-dev-classification |
| s3:ObjectCreated:* | par-servicios-poc/CECRL/ | par-servicios-poc-112636930635-dev-classification |
| s3:ObjectCreated:* | par-servicios-poc/RUT/ | par-servicios-poc-112636930635-dev-classification |
| s3:ObjectCreated:* | par-servicios-poc/RUB/ | par-servicios-poc-112636930635-dev-classification |
| s3:ObjectCreated:* | par-servicios-poc/ACC/ | par-servicios-poc-112636930635-dev-classification |

**Ambiente QA:**

| Evento | Prefijo | Destino |
|--------|---------|---------|
| s3:ObjectCreated:* | par-servicios-poc/CERL/ | par-servicios-poc-112636930635-qa-classification |
| s3:ObjectCreated:* | par-servicios-poc/CECRL/ | par-servicios-poc-112636930635-qa-classification |
| s3:ObjectCreated:* | par-servicios-poc/RUT/ | par-servicios-poc-112636930635-qa-classification |
| s3:ObjectCreated:* | par-servicios-poc/RUB/ | par-servicios-poc-112636930635-qa-classification |
| s3:ObjectCreated:* | par-servicios-poc/ACC/ | par-servicios-poc-112636930635-qa-classification |

#### Mapeo de eventos SQS a Lambda

| Ambiente | Origen | Destino |
|----------|--------|---------|
| DEV | par-servicios-poc-extraction-queue | par-servicios-poc-112636930635-dev-extraction-scoring |
| QA | par-servicios-poc-qa-extraction-queue | par-servicios-poc-112636930635-qa-extraction-scoring |

---

## 5. Seguridad

### 5.1. Encriptación en reposo
Se ha implementado encriptación en reposo para todos los buckets S3 utilizando el método de encriptación SSE-S3 (AES-256).

### 5.2. Políticas IAM

#### Roles IAM por ambiente

| Rol | Ambiente DEV | Ambiente QA |
|-----|-------------|------------|
| **Clasificación** | par-servicios-poc-112636930635-dev-classification | par-servicios-poc-112636930635-qa-classification |
| ARN | arn:aws:iam::112636930635:role/par-servicios-poc-112636930635-dev-classification | arn:aws:iam::112636930635:role/par-servicios-poc-112636930635-qa-classification |
| **Extracción y puntuación** | par-servicios-poc-112636930635-dev-extraction-scoring | par-servicios-poc-112636930635-qa-extraction-scoring |
| ARN | arn:aws:iam::112636930635:role/par-servicios-poc-112636930635-dev-extraction-scoring | arn:aws:iam::112636930635:role/par-servicios-poc-112636930635-qa-extraction-scoring |

**Permisos comunes para ambos ambientes:**
- Acceso completo a los buckets S3 de entrada y salida correspondientes al ambiente
- Acceso completo a las colas SQS correspondientes al ambiente
- Acceso completo a los servicios de Amazon Bedrock
- Permisos para escribir logs en CloudWatch
