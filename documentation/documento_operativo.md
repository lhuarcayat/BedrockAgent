# Documento Operativo
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
2. [Manuales](#2-manuales)
   1. [Procesamiento de Documentos](#procesamiento-de-documentos)
      1. [Carga de Documentos](#carga-de-documentos)
      2. [Estructura de Carpetas](#estructura-de-carpetas)
   2. [Verificación de Resultados](#verificación-de-resultados)
      1. [Acceso a Resultados JSON](#acceso-a-resultados-json)
      2. [Interpretación de Resultados](#interpretación-de-resultados)
   3. [Revisión Manual](#revisión-manual)
      1. [Casos de Baja Confianza](#casos-de-baja-confianza)
      2. [Corrección de Extracciones](#corrección-de-extracciones)

---

## 1. Descripción
El presente documento contiene guías operativas para el uso del sistema de procesamiento de documentos Par Servicios con Amazon Bedrock. Este sistema permite la extracción automatizada de información estructurada de diferentes tipos de documentos empresariales utilizando modelos de inteligencia artificial.

El sistema procesa cinco tipos de documentos:
- Certificados de Existencia y Representación Legal (CERL)
- Copia de cédulas de ciudadanía del Representante Legal (CECRL)
- Registro Único Tributario (RUT)
- Registro Único de Beneficiarios (RUB)
- Composiciones Accionarias (ACC)

---

## 2. Manuales

### Procesamiento de Documentos

#### Carga de Documentos
1. Acceda al bucket S3 "Document Filing Desk" designado para su ambiente (DEV o QA).
2. Navegue a la carpeta correspondiente al tipo de documento que desea procesar.
3. Cargue el documento en formato PDF.
4. El sistema iniciará automáticamente el procesamiento del documento.
5. Puede verificar el estado del procesamiento consultando el bucket de resultados JSON.

#### Estructura de Carpetas
Para asegurar el correcto procesamiento de los documentos, es importante cargarlos en la carpeta adecuada según su tipo:

```
par-servicios-poc/CERL/     # Certificados de Existencia y Representación Legal
par-servicios-poc/CECRL/    # Copia de cédulas de ciudadanía del Representante Legal
par-servicios-poc/RUT/      # Registro Único Tributario
par-servicios-poc/RUB/      # Registro Único de Beneficiarios
par-servicios-poc/ACC/      # Composiciones Accionarias
```

### Verificación de Resultados

#### Acceso a Resultados JSON
1. Una vez procesado el documento, acceda al bucket S3 "JSON Results".
2. Navegue a la carpeta correspondiente al tipo de documento procesado.
3. Descargue el archivo JSON generado.
4. El nombre del archivo JSON corresponderá al nombre del documento original con extensión .json.

#### Interpretación de Resultados
Los resultados de la extracción se presentan en formato JSON estructurado según el tipo de documento. Para interpretar correctamente los campos extraídos, consulte el [Manual de Mapeo de Campos](manual_mapeo_campos.md) que detalla la correspondencia entre los campos JSON y los datos en el documento original.

Ejemplo de estructura JSON para un Certificado de Existencia y Representación Legal (CERL):
```json
{
  "companyName": "EMPAQUETADURAS Y EMPAQUES S.A.",
  "companyType": "Sociedad Anónima",
  "country": "COLOMBIA",
  "documentType": "NIT",
  "taxId": "890915475-1",
  "mainAddress": "Carrera 52 23 54, MEDELLÍN",
  "incorporationDate": "1975-08-12",
  "companyDuration": "2046-03-15",
  "registrationNumber": "21-025485-04",
  "size": "MEDIANA EMPRESA",
  "relatedParties": [
    {
      "firstName": "MANUEL",
      "lastName": "JARAMILLO HENAO",
      "identificationType": "C.C.",
      "identificationNumber": "71.596.445",
      "relationshipType": "Gerente"
    }
  ],
  "embargoes": "",
  "liquidations": "",
  "lastRegistrationRenewalDate": "2024-03-19"
}
```

### Revisión Manual

#### Casos de Baja Confianza
Cuando el sistema no puede extraer información con alta confianza, el documento se marca para revisión manual:

1. Recibirá una notificación indicando que un documento requiere revisión.
2. Acceda al bucket S3 "JSON Results" y localice el archivo JSON correspondiente.
3. Los campos con baja confianza estarán marcados con un indicador de confianza bajo.
4. Compare la información extraída con el documento original.

#### Corrección de Extracciones
Para corregir extracciones con errores o baja confianza:

1. Abra el archivo JSON en un editor de texto.
2. Modifique los campos incorrectos según la información del documento original.
3. Guarde el archivo JSON corregido.
4. Cargue el archivo JSON corregido al bucket S3 "JSON Results" en la carpeta correspondiente.
5. El sistema registrará la corrección manual y la utilizará para mejorar futuras extracciones.

---

**Nota**: Para información detallada sobre los campos específicos de cada tipo de documento y ejemplos de estructuras JSON, consulte el [Manual de Mapeo de Campos](manual_mapeo_campos.md).
