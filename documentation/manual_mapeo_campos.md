# Manual de Mapeo de Campos para Extracción de Datos

Este manual proporciona una guía detallada para identificar los campos JSON correspondientes a los datos extraídos de diferentes tipos de documentos. Esto facilitará la verificación de la correcta extracción de información.

## Índice

- [Certificados de Existencia y Representación Legal (CERL)](#certificados-de-existencia-y-representación-legal-cerl)
- [Copia de cédulas de ciudadanía del Representante Legal (CECRL)](#copia-de-cédulas-de-ciudadanía-del-representante-legal-cecrl)
- [Registro único tributario (RUT)](#registro-único-tributario-rut)
- [Registro Único de Beneficiarios (RUB)](#registro-único-de-beneficiarios-rub)
- [Composiciones Accionarias (ACC)](#composiciones-accionarias-acc)

---

## Certificados de Existencia y Representación Legal (CERL)

### Datos a Extraer y Campos JSON Correspondientes

| Dato a Extraer | Campo JSON | Descripción | Ejemplo |
|----------------|------------|-------------|---------|
| Razón Social | `companyName` | Nombre completo de la empresa | "EMPAQUETADURAS Y EMPAQUES S.A." |
| NIT | `taxId` | Número de Identificación Tributaria | "890915475-1" |
| Dirección principal | `mainAddress` | Dirección completa de la sede principal | "Carrera 52 23 54, MEDELLÍN" |
| Fecha de constitución | `incorporationDate` | Fecha de creación de la empresa (formato YYYY-MM-DD) | "1975-08-12" |
| Duración de la sociedad | `companyDuration` | Fecha hasta la cual está vigente la sociedad (formato YYYY-MM-DD) | "2046-03-15" |
| Número de matrícula | `registrationNumber` | Número de registro mercantil | "21-025485-04" |
| Tamaño | `size` | Clasificación del tamaño de la empresa | "MEDIANA EMPRESA" |
| **Relacionados** | `relatedParties` | Array de personas relacionadas con la empresa | Ver detalle abajo |
| Embargos | `embargoes` | Información sobre embargos (si existen) | "" |
| Liquidaciones | `liquidations` | Información sobre liquidaciones (si existen) | "" |
| Fecha de emisión del documento | `documentIssueDate` | Fecha en que se emitió el certificado | "2024-03-19" |
| Fecha de última renovación de la matrícula | `lastRegistrationRenewalDate` | Fecha de la última renovación mercantil | "2024-03-19" |

### Estructura de Relacionados (`relatedParties`)

Los relacionados pueden ser personas o empresas. El esquema distingue entre ambos tipos:

#### Personas Relacionadas

| Dato a Extraer | Campo JSON | Descripción | Ejemplo |
|----------------|------------|-------------|---------|
| Nombre | `firstName` | Nombre(s) de la persona | "MANUEL" |
| Apellido | `lastName` | Apellido(s) de la persona | "JARAMILLO HENAO" |
| Tipo de identificación | `identificationType` | Tipo de documento de identidad | "C.C." |
| Identificación | `identificationNumber` | Número de identificación | "71.596.445" |
| Tipo de relación | `relationshipType` | Cargo o relación con la empresa | "Gerente" |

#### Empresas Relacionadas

| Dato a Extraer | Campo JSON | Descripción | Ejemplo |
|----------------|------------|-------------|---------|
| Razón Social | `companyName` | Nombre de la empresa relacionada | "INVERSIONES XYZ S.A." |
| Tipo de identificación | `identificationType` | Tipo de documento de identidad | "NIT" |
| Identificación | `identificationNumber` | Número de identificación | "900.123.456-7" |
| Tipo de relación | `relationshipType` | Tipo de relación con la empresa principal | "Accionista" |

### Ejemplo Completo

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
    },
    {
      "firstName": "ALBA NORA",
      "lastName": "AGUDELO ARANGO",
      "identificationType": "C.C.",
      "identificationNumber": "43.020.821",
      "relationshipType": "Miembro Principal Junta Directiva"
    },
    {
      "companyName": "INVERSIONES CORPORATIVAS S.A.",
      "identificationType": "NIT",
      "identificationNumber": "900.456.789-1",
      "relationshipType": "Accionista Mayoritario"
    }
  ],
  "embargoes": "",
  "liquidations": "",
  "lastRegistrationRenewalDate": "2024-03-19"
}
```

---

## Copia de cédulas de ciudadanía del Representante Legal (CECRL)

### Datos a Extraer y Campos JSON Correspondientes

| Dato a Extraer | Campo JSON | Descripción | Ejemplo |
|----------------|------------|-------------|---------|
| Nombre | `firstName` | Nombre(s) de la persona | "Monica" |
| Apellido | `lastName` | Apellido(s) de la persona | "Cataldo" |
| Tipo de documento | `identificationType` | Tipo de documento de identidad | "Cédula de Extranjería" |
| Número de identificación | `identificationNumber` | Número de identificación | "7908085" |
| País emisor | `country_issuer` | País que emitió el documento | "Colombia" |
| Nacionalidad | `nationality` | Nacionalidad de la persona | "Italia" |

### Ejemplo

```json
{
  "firstName": "Monica",
  "lastName": "Cataldo",
  "country_issuer": "Colombia",
  "nationality": "Italia",
  "identificationType": "Cédula de Extranjería",
  "identificationNumber": "7908085"
}
```

---

## Registro Único Tributario (RUT)

### Datos a Extraer y Campos JSON Correspondientes

| Dato a Extraer | Campo JSON | Descripción | Ejemplo |
|----------------|------------|-------------|---------|
| Razón Social | `companyName` | Nombre completo de la empresa | "SDV COLOMBIA SAS" |
| NIT | `taxId` | Número de Identificación Tributaria sin dígito de verificación | "830012771" |
| Dígito de Verificación | `verificationDigit` | Dígito de verificación del NIT | "3" |
| Tipo de Persona | `personType` | Clasificación como persona natural o jurídica | "Persona Jurídica" |
| **Relacionados** | `relatedParties` | Array de personas relacionadas con la empresa | Ver detalle abajo |
| Dirección | `address` | Dirección completa incluyendo municipio y departamento | "KM 34 AUT TUNJA ENTRADA NORTE VEREDA SAN MARTIN LT EL CHARCO DIAGONAL A LA FABRICA DE PAPEL, Gachancipa, Cundinamarca" |
| Fecha generación documento PDF | `documentGenerationDate` | Fecha en que se generó el documento RUT | "2024-07-16" |

### Estructura de Relacionados (`relatedParties`)

Los relacionados pueden ser personas o empresas. El esquema distingue entre ambos tipos:

#### Personas Relacionadas

| Dato a Extraer | Campo JSON | Descripción | Ejemplo |
|----------------|------------|-------------|---------|
| Nombre | `firstName` | Nombre(s) de la persona | "ALFONSO ANGEL" |
| Apellido | `lastName` | Apellido(s) de la persona | "QUIÑONES MORALES" |
| Tipo de identificación | `identificationType` | Tipo de documento de identidad | "Cédula de Ciudadanía" |
| Número de identificación | `identificationNumber` | Número de identificación | "72252799" |
| Tipo de relación | `relationshipType` | Cargo o relación con la empresa | "REPRS LEGAL PRIN" |

#### Empresas Relacionadas

| Dato a Extraer | Campo JSON | Descripción | Ejemplo |
|----------------|------------|-------------|---------|
| Razón Social | `companyName` | Nombre de la empresa relacionada | "GRUPO EMPRESARIAL XYZ" |
| Tipo de identificación | `identificationType` | Tipo de documento de identidad | "NIT" |
| Identificación | `identificationNumber` | Número de identificación | "900.789.123-5" |
| Tipo de relación | `relationshipType` | Tipo de relación con la empresa principal | "Socio" |

### Ejemplo Completo

```json
{
  "companyName": "SDV COLOMBIA SAS",
  "country": "COLOMBIA",
  "documentType": "NIT",
  "taxId": "830012771",
  "verificationDigit": "3",
  "personType": "Persona Jurídica",
  "relatedParties": [
    {
      "identificationType": "Cédula de Ciudadanía",
      "identificationNumber": "72252799",
      "relationshipType": "REPRS LEGAL PRIN",
      "firstName": "ALFONSO ANGEL",
      "lastName": "QUIÑONES MORALES"
    },
    {
      "identificationType": "Cédula de Ciudadanía",
      "identificationNumber": "52929474",
      "relationshipType": "REPRS LEGAL SUPL",
      "firstName": "SANDRA JULIANA",
      "lastName": "QUINTERO LOPEZ"
    },
    {
      "companyName": "GRUPO EMPRESARIAL XYZ",
      "identificationType": "NIT",
      "identificationNumber": "900.789.123-5",
      "relationshipType": "Socio"
    }
  ],
  "address": "KM 34 AUT TUNJA ENTRADA NORTE VEREDA SAN MARTIN LT EL CHARCO DIAGONAL A LA FABRICA DE PAPEL, Gachancipa, Cundinamarca",
  "documentGenerationDate": "2024-07-16"
}
```

---

## Registro Único de Beneficiarios (RUB)

### Datos a Extraer y Campos JSON Correspondientes

| Dato a Extraer | Campo JSON | Descripción | Ejemplo |
|----------------|------------|-------------|---------|
| Razón Social | `companyName` | Nombre completo de la empresa | "SONDA DE COLOMBIA SA" |
| NIT | `taxId` | Número de Identificación Tributaria | "1830001637" |
| **Relacionados** | `relatedParties` | Array de personas relacionadas con la empresa | Ver detalle abajo |

### Estructura de Relacionados (`relatedParties`)

En el RUB, los relacionados generalmente son personas, pero el esquema podría adaptarse para incluir empresas. A continuación se detalla la estructura para personas:

#### Personas Relacionadas

| Dato a Extraer | Campo JSON | Descripción | Ejemplo |
|----------------|------------|-------------|---------|
| Nombre | `firstName` | Nombre(s) de la persona | "ANDRES" |
| Apellido | `lastName` | Apellido(s) de la persona | "NAVARRO HAEUSSLER" |
| Tipo de identificación | `identificationType` | Tipo de documento de identidad (código) | "4" |
| Número de identificación | `identificationNumber` | Número de identificación | "25078702" |
| Tipo de Novedad | `noveltyType` | Tipo de novedad reportada | "Registro" |
| % de participación | `participationPercentage` | Porcentaje de participación (sin símbolo %) | "13.49" |

> **Nota sobre los tipos de identificación**: En el RUB, los tipos de identificación suelen representarse con códigos numéricos conforme a lo determinado por la autoridad emisora del documento.

### Ejemplo Completo

```json
{
  "companyName": "SONDA DE COLOMBIA SA",
  "documentType": "NIT",
  "taxId": "1830001637",
  "country": "Colombia",
  "relatedParties": [
    {
      "firstName": "ANDRES",
      "lastName": "NAVARRO HAEUSSLER",
      "identificationType": "4",
      "identificationNumber": "25078702",
      "noveltyType": "Registro",
      "participationPercentage": "13.49"
    },
    {
      "firstName": "PABLO",
      "lastName": "NAVARRO HAEUSSLLER",
      "identificationType": "4",
      "identificationNumber": "64416626",
      "noveltyType": "Registro",
      "participationPercentage": "5.41"
    },
    {
      "firstName": "MARIA ELENA",
      "lastName": "RODRIGUEZ PEREZ",
      "identificationType": "1",
      "identificationNumber": "52345678",
      "noveltyType": "Alta",
      "participationPercentage": "8.25"
    }
  ]
}
```

---

## Composiciones Accionarias (ACC)

### Datos a Extraer y Campos JSON Correspondientes

| Dato a Extraer | Campo JSON | Descripción | Ejemplo |
|----------------|------------|-------------|---------|
| Razón Social | `companyName` | Nombre completo de la empresa | "BUSINESS PROCESS MANAGEMENT LATINOAMERICA" |
| NIT | `taxId` | Número de Identificación Tributaria | "900.266.513-3" |
| **Relacionados** | `relatedParties` | Array de personas relacionadas con la empresa | Ver detalle abajo |

### Estructura de Relacionados (`relatedParties`)

En las Composiciones Accionarias, los relacionados pueden ser tanto personas como empresas. El esquema permite ambos tipos:

#### Personas Relacionadas (Accionistas Individuales)

| Dato a Extraer | Campo JSON | Descripción | Ejemplo |
|----------------|------------|-------------|---------|
| Nombre | `firstName` | Nombre(s) de la persona | "Mauricio" |
| Apellido | `lastName` | Apellido(s) de la persona | "Obregon Gutierrez" |
| Tipo de identificación | `identificationType` | Tipo de documento de identidad | "CC" |
| Número de identificación | `identificationNumber` | Número de identificación | "79.425.769" |
| Tipo de Relación | `relationshipType` | Tipo de relación con la empresa | "Shareholder" |
| % de participación | `participationPercentage` | Porcentaje de participación (sin símbolo %) | "80.0" |

#### Empresas Relacionadas (Accionistas Corporativos)

| Dato a Extraer | Campo JSON | Descripción | Ejemplo |
|----------------|------------|-------------|---------|
| Razón Social | `companyName` | Nombre de la empresa accionista | "INVERSIONES GLOBALES S.A." |
| Tipo de identificación | `identificationType` | Tipo de documento de identidad | "NIT" |
| Identificación | `identificationNumber` | Número de identificación | "800.123.456-7" |
| Tipo de Relación | `relationshipType` | Tipo de relación con la empresa | "Corporate Shareholder" |
| % de participación | `participationPercentage` | Porcentaje de participación (sin símbolo %) | "35.5" |

### Ejemplo Completo

```json
{
  "companyName": "BUSINESS PROCESS MANAGEMENT LATINOAMERICA",
  "documentType": "NIT",
  "taxId": "900.266.513-3",
  "relatedParties": [
    {
      "firstName": "Mauricio",
      "lastName": "Obregon Gutierrez",
      "identificationType": "CC",
      "identificationNumber": "79.425.769",
      "relationshipType": "Shareholder",
      "participationPercentage": "45.0"
    },
    {
      "firstName": "Monica María",
      "lastName": "Gutierrez Obregon",
      "identificationType": "CC",
      "identificationNumber": "52.123.456",
      "relationshipType": "Shareholder",
      "participationPercentage": "20.0"
    },
    {
      "companyName": "INVERSIONES GLOBALES S.A.",
      "identificationType": "NIT",
      "identificationNumber": "800.123.456-7",
      "relationshipType": "Corporate Shareholder",
      "participationPercentage": "35.0"
    }
  ]
}
```

---

## Notas Importantes

- Los campos pueden variar ligeramente dependiendo de la versión del documento.
- Algunos campos pueden estar vacíos si la información no está disponible en el documento original.
- En caso de discrepancias, siempre prevalece la información del documento original.
- Los tipos de identificación pueden aparecer en diferentes formatos según el documento (códigos numéricos, abreviaturas o nombres completos).
- En algunos casos, las empresas relacionadas pueden tener estructuras adicionales no mostradas en los ejemplos básicos.
- Es posible que en algunos casos una misma persona relacionada aparezca 2 veces, ello ocurre porque puede encontrarse que aparezca 2 veces en el documento (ej, Representante Legal y Socio / Director al mismo tiempo)
