# particle_effects_data.py

PARTICLE_EFFECT_LUT = {
    "smoke10": {
        "ParticleStandard": {
            "Flags": 3,
            "Emitters": [
                {
                    "ParticlePropsId": 64672,
                    "EmitterPropsId": 49328,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 75,
                    "EmitterStandard": {
                        "Seed": 0,
                        "MaxParticles": 75,
                        "Force": {
                            "x": 50.71419,
                            "y": -5.2453665E-06,
                            "z": -108.756935
                        },
                        "EmitterPosition": {"x": 0, "y": 0, "z": 0},
                        "EmitterSize": {"x": 0.5, "y": 0.5, "z": 0.5},
                        "TimeBetweenEmissions": 0.5,
                        "TimeBetweenEmissionsRandom": 0.33333334,
                        "NumParticlesPerEmission": 5,
                        "NumParticlesPerEmissionRandom": 1,
                        "InitialVelocity": 200,
                        "InitialVelocityRandom": 100,
                        "ParticleLife": 2,
                        "ParticleLifeRandom": 0.33333334,
                        "InitialDirection": {"x": 0, "y": 0, "z": 32},
                        "InitialDirectionRandom": {"x": 2, "y": 2, "z": 0.02},
                        "ParticleSize": {"x": 1, "y": 1, "z": -2.3509886e-38},
                        "Color": {"red": 128, "green": 255, "blue": 255, "alpha": 255},
                        "TextureCoordinates": [
                            {"x": 0, "y": 0},
                            {"x": 1, "y": 1},
                            {"x": 1.33e-42, "y": 1.309e-42},
                            {"x": 1.345e-42, "y": 1.28e-42}
                        ],
                        "ParticleTexture": {
                            "texture": "smoke10",
                            "textureAlpha": "",
                            "FilterAddressing": {
                                "FilterMode": "Linear_MipMap_Linear",
                                "AddressModeU": "Wrap",
                                "AddressModeV": "Wrap"
                            },
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {"red": 38, "green": 38, "blue": 38, "alpha": 127.5},
                        "StartColorRandom": {"red": 0, "green": 0, "blue": 0, "alpha": 0},
                        "EndColor": {"red": 69, "green": 69, "blue": 69, "alpha": 25.5},
                        "EndColorRandom": {"red": 0, "green": 0, "blue": 0, "alpha": 0}
                    },
                    "TextureCoordinates": {
                        "StartUV0": {"x": 0, "y": 0},
                        "StartUV0Random": {"x": 0, "y": 0},
                        "EndUV0": {"x": 0.90000004, "y": 0},
                        "EndUV0Random": {"x": 0, "y": 0},
                        "StartUV1": {"x": 0.1, "y": 1},
                        "StartUV1Random": {"x": 0, "y": 0},
                        "EndUV1": {"x": 1, "y": 1},
                        "EndUV1Random": {"x": 0, "y": 0}
                    },
                    "Matrix": None,
                    "ParticleSize": {
                        "StartSize": {"x": 50, "y": 50},
                        "StartSizeRandom": {"x": 0, "y": 0},
                        "EndSize": {"x": 300, "y": 600},
                        "EndSizeRandom": {"x": 200, "y": 400}
                    },
                    "Rotate": {
                        "StartRotate": 0,
                        "StartRotateRandom": 5,
                        "EndRotate": 0,
                        "EndRotateRandom": 45
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": None,
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": {
                        "List": [
                            {
                                "Time": 0.1,
                                "TimeBias": 0,
                                "MidColor": {"red": 38, "green": 38, "blue": 38, "alpha": 127.5},
                                "MidColorBias": {"red": 2, "green": 2, "blue": 2, "alpha": 0}
                            },
                            {
                                "Time": 0.25,
                                "TimeBias": 0,
                                "MidColor": {"red": 38, "green": 38, "blue": 38, "alpha": 127.5},
                                "MidColorBias": {"red": 0, "green": 0, "blue": 0, "alpha": 0}
                            },
                            {
                                "Time": 0.5,
                                "TimeBias": 0,
                                "MidColor": {"red": 55.000004, "green": 55.000004, "blue": 55.000004, "alpha": 51},
                                "MidColorBias": {"red": 0, "green": 0, "blue": 0, "alpha": 0}
                            }
                        ]
                    },
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": {
                        "List": [
                            {
                                "Time": 0.2,
                                "TimeBias": 0,
                                "MidSize": {"x": 150, "y": 200},
                                "MidSizeBias": {"x": 100, "y": 140}
                            },
                            {
                                "Time": 0.5,
                                "TimeBias": 0,
                                "MidSize": {"x": 200, "y": 300},
                                "MidSizeBias": {"x": 100, "y": 400}
                            },
                            {
                                "Time": 0.75,
                                "TimeBias": 0,
                                "MidSize": {"x": 200, "y": 500},
                                "MidSizeBias": {"x": 200, "y": 400}
                            }
                        ]
                    },
                    "AdvMultiTexCoordsStep": {
                        "List": [
                            {
                                "Time": 0.1,
                                "TimeBias": 0,
                                "MidUV0": {"u": 0.1, "v": 0},
                                "MidUV0Bias": {"u": 0, "v": 0},
                                "MidUV1": {"u": 0.2, "v": 1},
                                "MidUV1Bias": {"u": 0, "v": 0}
                            },
                            {
                                "Time": 0.2,
                                "TimeBias": 0,
                                "MidUV0": {"u": 0.2, "v": 0},
                                "MidUV0Bias": {"u": 0, "v": 0},
                                "MidUV1": {"u": 0.3, "v": 1},
                                "MidUV1Bias": {"u": 0, "v": 0}
                            },
                            {
                                "Time": 0.3,
                                "TimeBias": 0,
                                "MidUV0": {"u": 0.3, "v": 0},
                                "MidUV0Bias": {"u": 0, "v": 0},
                                "MidUV1": {"u": 0.4, "v": 1},
                                "MidUV1Bias": {"u": 0, "v": 0}
                            },
                            {
                                "Time": 0.4,
                                "TimeBias": 0,
                                "MidUV0": {"u": 0.4, "v": 0},
                                "MidUV0Bias": {"u": 0, "v": 0},
                                "MidUV1": {"u": 0.5, "v": 1},
                                "MidUV1Bias": {"u": 0, "v": 0}
                            },
                            {
                                "Time": 0.5,
                                "TimeBias": 0,
                                "MidUV0": {"u": 0.5, "v": 0},
                                "MidUV0Bias": {"u": 0, "v": 0},
                                "MidUV1": {"u": 0.6, "v": 1},
                                "MidUV1Bias": {"u": 0, "v": 0}
                            },
                            {
                                "Time": 0.6,
                                "TimeBias": 0,
                                "MidUV0": {"u": 0.6, "v": 0},
                                "MidUV0Bias": {"u": 0, "v": 0},
                                "MidUV1": {"u": 0.7, "v": 1},
                                "MidUV1Bias": {"u": 0, "v": 0}
                            },
                            {
                                "Time": 0.7,
                                "TimeBias": 0,
                                "MidUV0": {"u": 0.7, "v": 0},
                                "MidUV0Bias": {"u": 0, "v": 0},
                                "MidUV1": {"u": 0.8, "v": 1},
                                "MidUV1Bias": {"u": 0, "v": 0}
                            },
                            {
                                "Time": 0.8,
                                "TimeBias": 0,
                                "MidUV0": {"u": 0.8, "v": 0},
                                "MidUV0Bias": {"u": 0, "v": 0},
                                "MidUV1": {"u": 0.90000004, "v": 1},
                                "MidUV1Bias": {"u": 0, "v": 0}
                            }
                        ]
                    }
                }
            ]
        }
    },
    "fire02": {
        "ParticleStandard": {
            "Flags": 3,
            "Emitters": [
                {
                    "ParticlePropsId": 19568,
                    "EmitterPropsId": 59536,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 48,
                    "EmitterStandard": {
                        "Seed": 1,
                        "MaxParticles": 48,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 0.5,
                            "y": 0.5,
                            "z": 0.5
                        },
                        "TimeBetweenEmissions": 0,
                        "TimeBetweenEmissionsRandom": 0,
                        "NumParticlesPerEmission": 1,
                        "NumParticlesPerEmissionRandom": 0,
                        "InitialVelocity": 0,
                        "InitialVelocityRandom": 0,
                        "ParticleLife": 0.8333334,
                        "ParticleLifeRandom": 0,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": 1
                        },
                        "InitialDirectionRandom": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "ParticleSize": {
                            "x": 80,
                            "y": 130
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 9.642894e-39,
                                "y": 9.183704e-39
                            },
                            {
                                "x": 1.0102052e-38,
                                "y": 1.44e-43
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "fire02",
                            "textureAlpha": "",
                            "FilterAddressing": {
                                "FilterMode": "Linear_MipMap_Linear",
                                "AddressModeU": "Wrap",
                                "AddressModeV": "Wrap"
                            },
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 250.00002,
                            "green": 250.00002,
                            "blue": 250.00002,
                            "alpha": 255
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 250.00002,
                            "green": 250.00002,
                            "blue": 250.00002,
                            "alpha": 255
                        },
                        "EndColorRandom": {
                            "red": 2,
                            "green": 2,
                            "blue": 2,
                            "alpha": 0
                        }
                    },
                    "TextureCoordinates": {
                        "StartUV0": {
                            "x": 0,
                            "y": 0
                        },
                        "StartUV0Random": {
                            "x": 0,
                            "y": 0
                        },
                        "EndUV0": {
                            "x": 0.91999996,
                            "y": 0
                        },
                        "EndUV0Random": {
                            "x": 0,
                            "y": 0
                        },
                        "StartUV1": {
                            "x": 0.04,
                            "y": 1
                        },
                        "StartUV1Random": {
                            "x": 0,
                            "y": 0
                        },
                        "EndUV1": {
                            "x": 0.96,
                            "y": 1
                        },
                        "EndUV1Random": {
                            "x": 0,
                            "y": 0
                        }
                    },
                    "Matrix": None,
                    "ParticleSize": None,
                    "Rotate": {
                        "StartRotate": -20,
                        "StartRotateRandom": 0,
                        "EndRotate": -20,
                        "EndRotateRandom": 0
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": {
                        "UseDirection": False,
                        "Random": False,
                        "PointList": [
                            {
                                "x": -1.6972677e-05,
                                "y": -2.2382583e-05,
                                "z": -2.8980601e-05
                            },
                            {
                                "x": 70.45405,
                                "y": 559.3705,
                                "z": 1319.3811
                            },
                            {
                                "x": 40.193428,
                                "y": 1108.8148,
                                "z": 1283.1187
                            },
                            {
                                "x": 11.097094,
                                "y": 753.883,
                                "z": 1338.8953
                            },
                            {
                                "x": 2.5581362,
                                "y": 908.9255,
                                "z": 1328.6627
                            },
                            {
                                "x": -863.7427,
                                "y": 836.85425,
                                "z": 1902.105
                            },
                            {
                                "x": -845.54034,
                                "y": 506.3539,
                                "z": 1923.9176
                            },
                            {
                                "x": -928.0423,
                                "y": 956.68036,
                                "z": 1906.472
                            },
                            {
                                "x": -1317.328,
                                "y": 935.824,
                                "z": 1915.3145
                            },
                            {
                                "x": -881.1258,
                                "y": 810.08435,
                                "z": 2644.3967
                            },
                            {
                                "x": -872.7234,
                                "y": 657.5209,
                                "z": 2654.4656
                            },
                            {
                                "x": -1040.4478,
                                "y": 949.52386,
                                "z": 2638.0938
                            },
                            {
                                "x": -1196.6864,
                                "y": 941.15326,
                                "z": 2641.6426
                            },
                            {
                                "x": -1104.2192,
                                "y": 1735.4486,
                                "z": 2018.3694
                            },
                            {
                                "x": -787.219,
                                "y": 1752.4321,
                                "z": 2011.1688
                            },
                            {
                                "x": -786.7644,
                                "y": 1783.8152,
                                "z": 1418.2747
                            }
                        ],
                        "DirectionList": []
                    },
                    "AdvCircle": None,
                    "AdvSphere": None,
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": None,
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": None,
                    "AdvMultiTexCoordsStep": {
                        "List": [
                            {
                                "Time": 0.041666668,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.04,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.08,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.083333336,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.08,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.12,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.125,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.12,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.16,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.16666667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.16,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.19999999,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.20833333,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.19999999,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.24,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.25,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.24,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.28,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.29166666,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.28,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.32,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.33333334,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.32,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.35999998,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.375,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.35999998,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.39999998,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.41666666,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.39999998,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.44,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.45833334,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.44,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.48,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.5,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.48,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.52,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.5416667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.52,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.56,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.5833333,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.56,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.59999996,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.625,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.59999996,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.64,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.6666667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.64,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.68,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.7083333,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.68,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.71999997,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.75,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.71999997,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.76,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.7916667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.76,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.79999995,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.8333333,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.79999995,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.84,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.875,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.84,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.88,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.9166667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.88,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.91999996,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            }
                        ]
                    }
                }
            ]
        }
    },
    "woodchip": {
        "ParticleStandard": {
            "Flags": 3,
            "Emitters": [
                {
                    "ParticlePropsId": 10304,
                    "EmitterPropsId": 19552,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 600,
                    "EmitterStandard": {
                        "Seed": 1,
                        "MaxParticles": 600,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": -300
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 119.2955,
                            "y": 119.2955,
                            "z": 119.2955
                        },
                        "TimeBetweenEmissions": 0.033333335,
                        "TimeBetweenEmissionsRandom": 0,
                        "NumParticlesPerEmission": 5,
                        "NumParticlesPerEmissionRandom": 0,
                        "InitialVelocity": 100,
                        "InitialVelocityRandom": 74.550385,
                        "ParticleLife": 0.6666667,
                        "ParticleLifeRandom": 0.33333334,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": 1
                        },
                        "InitialDirectionRandom": {
                            "x": 0.1,
                            "y": 0.1,
                            "z": 0
                        },
                        "ParticleSize": {
                            "x": 10,
                            "y": 7
                        },
                        "ParticleSize_SeriMisstake": 2147483647,
                        "Color": {
                            "red": 127,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 1.8e-44,
                                "y": 1.5e-44
                            },
                            {
                                "x": 6.6e-44,
                                "y": 2.17e-43
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "woodchip",
                            "textureAlpha": "",
                            "FilterAddressing": {
                                "FilterMode": "Linear_MipMap_Linear",
                                "AddressModeU": "Wrap",
                                "AddressModeV": "Wrap"
                            },
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": None,
                    "TextureCoordinates": None,
                    "Matrix": None,
                    "ParticleSize": None,
                    "Rotate": {
                        "StartRotate": 0,
                        "StartRotateRandom": 90,
                        "EndRotate": 90,
                        "EndRotateRandom": 180
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": {
                        "Radius": 3.7277482,
                        "RadiusGap": 0.5,
                        "UseSphereEmission": True
                    },
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": None,
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": None,
                    "AdvMultiTexCoordsStep": None
                }
            ]
        }
    },
    "PB_Weathermachine_lightning": {
        "ParticleStandard": {
            "Flags": 3,
            "Emitters": [
                {
                    "ParticlePropsId": 19568,
                    "EmitterPropsId": 60560,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 41,
                    "EmitterStandard": {
                        "Seed": 1,
                        "MaxParticles": 41,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 32.68158,
                            "y": 32.68158,
                            "z": 60.227192
                        },
                        "TimeBetweenEmissions": 0,
                        "TimeBetweenEmissionsRandom": 0,
                        "NumParticlesPerEmission": 13,
                        "NumParticlesPerEmissionRandom": 23,
                        "InitialVelocity": 0,
                        "InitialVelocityRandom": 20,
                        "ParticleLife": 0.06666667,
                        "ParticleLifeRandom": 0.13333334,
                        "InitialDirection": {
                            "x": 2.27,
                            "y": 0,
                            "z": 1
                        },
                        "InitialDirectionRandom": {
                            "x": 0.5,
                            "y": 0.5,
                            "z": 0.5
                        },
                        "ParticleSize": {
                            "x": 200,
                            "y": 60
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 4.65e-43,
                                "y": 6.383398e-10
                            },
                            {
                                "x": 6.82e-43,
                                "y": 4.59184e-40
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "PB_Weathermachine_lightning",
                            "textureAlpha": "",
                            "FilterAddressing": {
                                "FilterMode": "Linear_MipMap_Linear",
                                "AddressModeU": "Wrap",
                                "AddressModeV": "Wrap"
                            },
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 255,
                            "green": 255,
                            "blue": 255,
                            "alpha": 204
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 84,
                            "green": 59.000004,
                            "blue": 211.00002,
                            "alpha": 127.5
                        },
                        "EndColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        }
                    },
                    "TextureCoordinates": {
                        "StartUV0": {
                            "x": 0,
                            "y": 0
                        },
                        "StartUV0Random": {
                            "x": 0,
                            "y": 0
                        },
                        "EndUV0": {
                            "x": 0,
                            "y": 0.75
                        },
                        "EndUV0Random": {
                            "x": 0,
                            "y": 0
                        },
                        "StartUV1": {
                            "x": 1,
                            "y": 0.25
                        },
                        "StartUV1Random": {
                            "x": 0,
                            "y": 0
                        },
                        "EndUV1": {
                            "x": 1,
                            "y": 1
                        },
                        "EndUV1Random": {
                            "x": 0,
                            "y": 0
                        }
                    },
                    "Matrix": None,
                    "ParticleSize": None,
                    "Rotate": {
                        "StartRotate": 30,
                        "StartRotateRandom": 30,
                        "EndRotate": 30,
                        "EndRotateRandom": 30
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": {
                        "Radius": 76.25696,
                        "RadiusGap": 0.5,
                        "Height": 60.227192,
                        "UseCircleEmission": False,
                        "DirRotation": 0
                    },
                    "AdvSphere": None,
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": None,
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": None,
                    "AdvMultiTexCoordsStep": {
                        "List": [
                            {
                                "Time": 0.25,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0,
                                    "v": 0.25
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 1,
                                    "v": 0.5
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.5,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0,
                                    "v": 0.5
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 1,
                                    "v": 0.75
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            }
                        ]
                    }
                }
            ]
        }
    },
    "sulfur_spray": {
        "ParticleStandard": {
            "Flags": 3,
            "Emitters": [
                {
                    "ParticlePropsId": 30816,
                    "EmitterPropsId": 31856,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 35,
                    "EmitterStandard": {
                        "Seed": 1,
                        "MaxParticles": 35,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 72.3574,
                            "y": 36.1787,
                            "z": 2.1707227
                        },
                        "TimeBetweenEmissions": 0.033333335,
                        "TimeBetweenEmissionsRandom": 0,
                        "NumParticlesPerEmission": 1,
                        "NumParticlesPerEmissionRandom": 0,
                        "InitialVelocity": 90,
                        "InitialVelocityRandom": 30,
                        "ParticleLife": 0.93333334,
                        "ParticleLifeRandom": 0.2,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": 1
                        },
                        "InitialDirectionRandom": {
                            "x": 0.1,
                            "y": 0.1,
                            "z": 0
                        },
                        "ParticleSize": {
                            "x": 75,
                            "y": 75
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 0,
                                "y": 0
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "sulfur_spray",
                            "textureAlpha": "",
                            "FilterAddressing": {
                                "FilterMode": "Linear_MipMap_Linear",
                                "AddressModeU": "Wrap",
                                "AddressModeV": "Wrap"
                            },
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        }
                    },
                    "TextureCoordinates": None,
                    "Matrix": None,
                    "ParticleSize": None,
                    "Rotate": {
                        "StartRotate": 0,
                        "StartRotateRandom": 0,
                        "EndRotate": 0,
                        "EndRotateRandom": 50.000004
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": None,
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": {
                        "List": [
                            {
                                "Time": 0.3,
                                "TimeBias": 0,
                                "MidColor": {
                                    "red": 255,
                                    "green": 255,
                                    "blue": 255,
                                    "alpha": 255
                                },
                                "MidColorBias": {
                                    "red": 0,
                                    "green": 0,
                                    "blue": 0,
                                    "alpha": 0
                                }
                            },
                            {
                                "Time": 0.6,
                                "TimeBias": 0,
                                "MidColor": {
                                    "red": 255,
                                    "green": 255,
                                    "blue": 255,
                                    "alpha": 255
                                },
                                "MidColorBias": {
                                    "red": 0,
                                    "green": 0,
                                    "blue": 0,
                                    "alpha": 0
                                }
                            }
                        ]
                    },
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": None,
                    "AdvMultiTexCoordsStep": None
                }
            ]
        }
    },
    "salimTrapIcon": {
        "ParticleStandard": {
            "Flags": 3,
            "Emitters": [
                {
                    "ParticlePropsId": 26704,
                    "EmitterPropsId": 52336,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 1,
                    "EmitterStandard": {
                        "Seed": 1,
                        "MaxParticles": 1,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 26.69075,
                            "y": 26.69075,
                            "z": 26.69075
                        },
                        "TimeBetweenEmissions": 2,
                        "TimeBetweenEmissionsRandom": 0,
                        "NumParticlesPerEmission": 1,
                        "NumParticlesPerEmissionRandom": 0,
                        "InitialVelocity": 0,
                        "InitialVelocityRandom": 0,
                        "ParticleLife": 1,
                        "ParticleLifeRandom": 0,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": 1
                        },
                        "InitialDirectionRandom": {
                            "x": 0.1,
                            "y": 0.1,
                            "z": 0
                        },
                        "ParticleSize": {
                            "x": 169.29698,
                            "y": 169.29698
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 1.01e-43,
                                "y": 8.7432e-32
                            },
                            {
                                "x": 1.11e-43,
                                "y": 1.836717e-39
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "salimTrapIcon",
                            "textureAlpha": "",
                            "FilterAddressing": {
                                "FilterMode": "Linear_MipMap_Linear",
                                "AddressModeU": "Wrap",
                                "AddressModeV": "Wrap"
                            },
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 255,
                            "green": 255,
                            "blue": 255,
                            "alpha": 0
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 255,
                            "green": 255,
                            "blue": 255,
                            "alpha": 0
                        },
                        "EndColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        }
                    },
                    "TextureCoordinates": None,
                    "Matrix": None,
                    "ParticleSize": None,
                    "Rotate": None,
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": {
                        "Radius": 0,
                        "RadiusGap": 0,
                        "UseSphereEmission": False
                    },
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": {
                        "List": [
                            {
                                "Time": 0.2,
                                "TimeBias": 0,
                                "MidColor": {
                                    "red": 255,
                                    "green": 255,
                                    "blue": 255,
                                    "alpha": 255
                                },
                                "MidColorBias": {
                                    "red": 0,
                                    "green": 0,
                                    "blue": 0,
                                    "alpha": 0
                                }
                            },
                            {
                                "Time": 0.8,
                                "TimeBias": 0,
                                "MidColor": {
                                    "red": 255,
                                    "green": 255,
                                    "blue": 255,
                                    "alpha": 255
                                },
                                "MidColorBias": {
                                    "red": 0,
                                    "green": 0,
                                    "blue": 0,
                                    "alpha": 0
                                }
                            }
                        ]
                    },
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": None,
                    "AdvMultiTexCoordsStep": None
                }
            ]
        }
    },
    "TMP_resourceGold_Sparkle": {
        "ParticleStandard": {
            "Flags": 3,
            "Emitters": [
                {
                    "ParticlePropsId": 57472,
                    "EmitterPropsId": 58512,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 5,
                    "EmitterStandard": {
                        "Seed": 1,
                        "MaxParticles": 5,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 150,
                            "y": 150,
                            "z": 5
                        },
                        "TimeBetweenEmissions": 0.06666667,
                        "TimeBetweenEmissionsRandom": 0.033333335,
                        "NumParticlesPerEmission": 1,
                        "NumParticlesPerEmissionRandom": 2,
                        "InitialVelocity": 1,
                        "InitialVelocityRandom": 20,
                        "ParticleLife": 0.33333334,
                        "ParticleLifeRandom": 0.33333334,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": -1
                        },
                        "InitialDirectionRandom": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "ParticleSize": {
                            "x": 1,
                            "y": 1
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 1.9420925e+31,
                                "y": 1.211889e+25
                            },
                            {
                                "x": 7.7100935e+28,
                                "y": 1.8037311e+28
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "TMP_resourceGold_Sparkle",
                            "textureAlpha": "",
                            "FilterAddressing": {
                                "FilterMode": "Linear_MipMap_Linear",
                                "AddressModeU": "Wrap",
                                "AddressModeV": "Wrap"
                            },
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 255,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 255,
                            "green": 127.5,
                            "blue": 0,
                            "alpha": 255
                        },
                        "EndColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        }
                    },
                    "TextureCoordinates": None,
                    "Matrix": None,
                    "ParticleSize": {
                        "StartSize": {
                            "x": 1.36765,
                            "y": 1.36765
                        },
                        "StartSizeRandom": {
                            "x": 0,
                            "y": 0
                        },
                        "EndSize": {
                            "x": 1.36765,
                            "y": 1.36765
                        },
                        "EndSizeRandom": {
                            "x": 0,
                            "y": 0
                        }
                    },
                    "Rotate": {
                        "StartRotate": 0,
                        "StartRotateRandom": 360,
                        "EndRotate": 0,
                        "EndRotateRandom": 180
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": None,
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": {
                        "List": [
                            {
                                "Time": 0.9,
                                "TimeBias": 0,
                                "MidColor": {
                                    "red": 255,
                                    "green": 255,
                                    "blue": 0,
                                    "alpha": 255
                                },
                                "MidColorBias": {
                                    "red": 0,
                                    "green": 0,
                                    "blue": 0,
                                    "alpha": 0
                                }
                            }
                        ]
                    },
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": {
                        "List": [
                            {
                                "Time": 0.25,
                                "TimeBias": 0,
                                "MidSize": {
                                    "x": 13.6765,
                                    "y": 13.6765
                                },
                                "MidSizeBias": {
                                    "x": 13.6765,
                                    "y": 13.6765
                                }
                            }
                        ]
                    },
                    "AdvMultiTexCoordsStep": None
                }
            ]
        }
    },

    "XD_StoneSparkles": {
        "ParticleStandard": {
            "Flags": 3,
            "Emitters": [
                {
                    "ParticlePropsId": 57472,
                    "EmitterPropsId": 58512,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 5,
                    "EmitterStandard": {
                        "Seed": 1,
                        "MaxParticles": 5,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 111.39,
                            "y": 136.5,
                            "z": 12.736
                        },
                        "TimeBetweenEmissions": 0,
                        "TimeBetweenEmissionsRandom": 0,
                        "NumParticlesPerEmission": 1,
                        "NumParticlesPerEmissionRandom": 0,
                        "InitialVelocity": 1,
                        "InitialVelocityRandom": 4,
                        "ParticleLife": 0.46666667,
                        "ParticleLifeRandom": 0.033333335,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": -1
                        },
                        "InitialDirectionRandom": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "ParticleSize": {
                            "x": 1,
                            "y": 1
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 2e-44,
                                "y": 2e-44
                            },
                            {
                                "x": 2e-44,
                                "y": 2.1e-44
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "XD_StoneSparkles",
                            "textureAlpha": "",
                            "FilterAddressing": {
                                "FilterMode": "Linear_MipMap_Linear",
                                "AddressModeU": "Wrap",
                                "AddressModeV": "Wrap"
                            },
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 255,
                            "green": 221.00002,
                            "blue": 191,
                            "alpha": 255
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 216.00002,
                            "green": 142,
                            "blue": 75,
                            "alpha": 0
                        },
                        "EndColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        }
                    },
                    "TextureCoordinates": None,
                    "Matrix": None,
                    "ParticleSize": {
                        "StartSize": {
                            "x": 20,
                            "y": 20
                        },
                        "StartSizeRandom": {
                            "x": 0,
                            "y": 0
                        },
                        "EndSize": {
                            "x": 1,
                            "y": 1
                        },
                        "EndSizeRandom": {
                            "x": 0,
                            "y": 0
                        }
                    },
                    "Rotate": {
                        "StartRotate": 0,
                        "StartRotateRandom": 360,
                        "EndRotate": 0,
                        "EndRotateRandom": 180
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": None,
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": {
                        "List": [
                            {
                                "Time": 0.9,
                                "TimeBias": 0,
                                "MidColor": {
                                    "red": 216.00002,
                                    "green": 142,
                                    "blue": 75,
                                    "alpha": 51
                                },
                                "MidColorBias": {
                                    "red": 0,
                                    "green": 0,
                                    "blue": 0,
                                    "alpha": 0
                                }
                            }
                        ]
                    },
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": {
                        "List": [
                            {
                                "Time": 0.25,
                                "TimeBias": 0,
                                "MidSize": {
                                    "x": 20,
                                    "y": 20
                                },
                                "MidSizeBias": {
                                    "x": 10,
                                    "y": 10
                                }
                            }
                        ]
                    },
                    "AdvMultiTexCoordsStep": None
                }
            ]
        }
    },

    "smoke11": {
        "ParticleStandard": {
            "Flags": 3,
            "Emitters": [
                {
                    "ParticlePropsId": 57472,
                    "EmitterPropsId": 58512,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 147,
                    "EmitterStandard": {
                        "Seed": 0,
                        "MaxParticles": 147,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 0.5,
                            "y": 0.5,
                            "z": 0.5
                        },
                        "TimeBetweenEmissions": 0.33333334,
                        "TimeBetweenEmissionsRandom": 0,
                        "NumParticlesPerEmission": 1,
                        "NumParticlesPerEmissionRandom": 0,
                        "InitialVelocity": 120.38401,
                        "InitialVelocityRandom": 56.1,
                        "ParticleLife": 7.5333333,
                        "ParticleLifeRandom": 0.23333333,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": 32
                        },
                        "InitialDirectionRandom": {
                            "x": 2,
                            "y": 2,
                            "z": 0.02
                        },
                        "ParticleSize": {
                            "x": 1,
                            "y": 1
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 8.6324516e-17,
                                "y": 5.51153e-40
                            },
                            {
                                "x": 7.34687e-40,
                                "y": 2.8967556e-35
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "smoke11",
                            "textureAlpha": "",
                            "FilterAddressing": {
                                "FilterMode": "Linear_MipMap_Linear",
                                "AddressModeU": "Wrap",
                                "AddressModeV": "Wrap"
                            },
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 221.00002,
                            "green": 136,
                            "blue": 102.00001,
                            "alpha": 0
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        }
                    },
                    "TextureCoordinates": None,
                    "Matrix": None,
                    "ParticleSize": {
                        "StartSize": {
                            "x": 120,
                            "y": 120
                        },
                        "StartSizeRandom": {
                            "x": 0,
                            "y": 0
                        },
                        "EndSize": {
                            "x": 198.31009,
                            "y": 705.9
                        },
                        "EndSizeRandom": {
                            "x": 22,
                            "y": 21
                        }
                    },
                    "Rotate": {
                        "StartRotate": 0,
                        "StartRotateRandom": 5,
                        "EndRotate": 0,
                        "EndRotateRandom": 18
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": None,
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": {
                        "List": [
                            {
                                "Time": 0.31,
                                "TimeBias": 0,
                                "MidColor": {
                                    "red": 223.00002,
                                    "green": 208.00002,
                                    "blue": 188,
                                    "alpha": 255
                                },
                                "MidColorBias": {
                                    "red": 2,
                                    "green": 2,
                                    "blue": 2,
                                    "alpha": 0
                                }
                            },
                            {
                                "Time": 0.39,
                                "TimeBias": 0,
                                "MidColor": {
                                    "red": 119.00001,
                                    "green": 119.00001,
                                    "blue": 119.00001,
                                    "alpha": 255
                                },
                                "MidColorBias": {
                                    "red": 0,
                                    "green": 0,
                                    "blue": 0,
                                    "alpha": 0
                                }
                            }
                        ]
                    },
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": {
                        "List": [
                            {
                                "Time": 0.1,
                                "TimeBias": 0,
                                "MidSize": {
                                    "x": 133.2473,
                                    "y": 328.02
                                },
                                "MidSizeBias": {
                                    "x": 74,
                                    "y": 25
                                }
                            }
                        ]
                    },
                    "AdvMultiTexCoordsStep": None
                }
            ]
        }
    },
    "XF_Leaves": {
        "ParticleStandard": {
            "Flags": 3,
            "Emitters": [
                {
                    "ParticlePropsId": 12368,
                    "EmitterPropsId": 13408,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 10,
                    "EmitterStandard": {
                        "Seed": 3,
                        "MaxParticles": 10,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 150,
                            "y": 150,
                            "z": 0.5
                        },
                        "TimeBetweenEmissions": 1,
                        "TimeBetweenEmissionsRandom": 0.93333334,
                        "NumParticlesPerEmission": 1,
                        "NumParticlesPerEmissionRandom": 0,
                        "InitialVelocity": 60,
                        "InitialVelocityRandom": 40,
                        "ParticleLife": 8,
                        "ParticleLifeRandom": 1.5,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": -1
                        },
                        "InitialDirectionRandom": {
                            "x": 0.1,
                            "y": 0.1,
                            "z": 0.5
                        },
                        "ParticleSize": {
                            "x": 13,
                            "y": 13
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 0.5,
                                "y": 0.5
                            },
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1e-45,
                                "y": 8.5721096e-36
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "XF_Leaves",
                            "textureAlpha": "",
                            "FilterAddressing": {
                                "FilterMode": "Linear_MipMap_Linear",
                                "AddressModeU": "Wrap",
                                "AddressModeV": "Wrap"
                            },
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 128,
                            "green": 128,
                            "blue": 128,
                            "alpha": 0
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 128,
                            "green": 128,
                            "blue": 128,
                            "alpha": 255
                        },
                        "EndColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        }
                    },
                    "TextureCoordinates": None,
                    "Matrix": None,
                    "ParticleSize": None,
                    "Rotate": {
                        "StartRotate": 0,
                        "StartRotateRandom": 5,
                        "EndRotate": 360,
                        "EndRotateRandom": 180
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": None,
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": None,
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": None,
                    "AdvMultiTexCoordsStep": None
                }
            ]
        }
    },
    "smoke12": {
        "ParticleStandard": {
            "Flags": 3,
            "Emitters": [
                {
                    "ParticlePropsId": 64672,
                    "EmitterPropsId": 49328,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 30,
                    "EmitterStandard": {
                        "Seed": 30,
                        "MaxParticles": 30,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 100,
                            "y": 100,
                            "z": 0.5
                        },
                        "TimeBetweenEmissions": 0.2,
                        "TimeBetweenEmissionsRandom": 0.1,
                        "NumParticlesPerEmission": 1,
                        "NumParticlesPerEmissionRandom": 0,
                        "InitialVelocity": 1.582859,
                        "InitialVelocityRandom": 2.7197943,
                        "ParticleLife": 2,
                        "ParticleLifeRandom": 0.33333334,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": -396.79013
                        },
                        "InitialDirectionRandom": {
                            "x": 2,
                            "y": 2,
                            "z": 0.02
                        },
                        "ParticleSize": {
                            "x": 1,
                            "y": 1
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 8.908151e-39,
                                "y": 7.347002e-39
                            },
                            {
                                "x": 1.0285723e-38,
                                "y": 6.704133e-39
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "smoke12",
                            "textureAlpha": "",
                            "FilterAddressing": {
                                "FilterMode": "Linear_MipMap_Linear",
                                "AddressModeU": "Wrap",
                                "AddressModeV": "Wrap"
                            },
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 148,
                            "green": 114.00001,
                            "blue": 77,
                            "alpha": 0
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 157,
                            "green": 150,
                            "blue": 124.00001,
                            "alpha": 0
                        },
                        "EndColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        }
                    },
                    "TextureCoordinates": {
                        "StartUV0": {
                            "x": 0,
                            "y": 0
                        },
                        "StartUV0Random": {
                            "x": 0,
                            "y": 0
                        },
                        "EndUV0": {
                            "x": 0.90000004,
                            "y": 0
                        },
                        "EndUV0Random": {
                            "x": 0,
                            "y": 0
                        },
                        "StartUV1": {
                            "x": 0.1,
                            "y": 1
                        },
                        "StartUV1Random": {
                            "x": 0,
                            "y": 0
                        },
                        "EndUV1": {
                            "x": 1,
                            "y": 1
                        },
                        "EndUV1Random": {
                            "x": 0,
                            "y": 0
                        }
                    },
                    "Matrix": None,
                    "ParticleSize": {
                        "StartSize": {
                            "x": 300,
                            "y": 250
                        },
                        "StartSizeRandom": {
                            "x": 30.841,
                            "y": 0
                        },
                        "EndSize": {
                            "x": 400,
                            "y": 268
                        },
                        "EndSizeRandom": {
                            "x": 50,
                            "y": 50
                        }
                    },
                    "Rotate": {
                        "StartRotate": 0,
                        "StartRotateRandom": 5,
                        "EndRotate": 0,
                        "EndRotateRandom": 45
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": None,
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": {
                        "List": [
                            {
                                "Time": 0.65999997,
                                "TimeBias": 0,
                                "MidColor": {
                                    "red": 255,
                                    "green": 242.00002,
                                    "blue": 191,
                                    "alpha": 127.5
                                },
                                "MidColorBias": {
                                    "red": 0,
                                    "green": 0,
                                    "blue": 0,
                                    "alpha": 0
                                }
                            }
                        ]
                    },
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": {
                        "List": [
                            {
                                "Time": 0.41000023,
                                "TimeBias": 0,
                                "MidSize": {
                                    "x": 350,
                                    "y": 350
                                },
                                "MidSizeBias": {
                                    "x": 40,
                                    "y": 40
                                }
                            }
                        ]
                    },
                    "AdvMultiTexCoordsStep": {
                        "List": [
                            {
                                "Time": 0.1,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.1,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.2,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.2,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.2,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.3,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.3,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.3,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.4,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.4,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.4,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.5,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.5,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.5,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.6,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.6,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.6,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.7,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.7,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.7,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.8,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.8,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.8,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.90000004,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            }
                        ]
                    }
                }
            ]
        }
    },
    "fire01": {
        "ParticleStandard": {
            "Flags": 3,
            "Emitters": [
                {
                    "ParticlePropsId": 19568,
                    "EmitterPropsId": 20608,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 10,
                    "EmitterStandard": {
                        "Seed": 0,
                        "MaxParticles": 10,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 0.5,
                            "y": 0.5,
                            "z": 0.5
                        },
                        "TimeBetweenEmissions": 0.033333335,
                        "TimeBetweenEmissionsRandom": 0,
                        "NumParticlesPerEmission": 1,
                        "NumParticlesPerEmissionRandom": 0,
                        "InitialVelocity": 5.45,
                        "InitialVelocityRandom": 0,
                        "ParticleLife": 0.8333334,
                        "ParticleLifeRandom": 0,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": 1
                        },
                        "InitialDirectionRandom": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "ParticleSize": {
                            "x": 200,
                            "y": 110
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 6.244926e-39,
                                "y": 8.724488e-39
                            },
                            {
                                "x": 4.68371e-39,
                                "y": 7.62248e-39
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "fire01",
                            "textureAlpha": "",
                            "FilterAddressing": {
                                "FilterMode": "Linear_MipMap_Linear",
                                "AddressModeU": "Wrap",
                                "AddressModeV": "Wrap"
                            },
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 250.00002,
                            "green": 250.00002,
                            "blue": 250.00002,
                            "alpha": 255
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 250.00002,
                            "green": 250.00002,
                            "blue": 250.00002,
                            "alpha": 255
                        },
                        "EndColorRandom": {
                            "red": 2,
                            "green": 2,
                            "blue": 2,
                            "alpha": 76.5
                        }
                    },
                    "TextureCoordinates": {
                        "StartUV0": {
                            "x": 0,
                            "y": 0
                        },
                        "StartUV0Random": {
                            "x": 0,
                            "y": 0
                        },
                        "EndUV0": {
                            "x": 0.91999996,
                            "y": 0
                        },
                        "EndUV0Random": {
                            "x": 0,
                            "y": 0
                        },
                        "StartUV1": {
                            "x": 0.04,
                            "y": 1
                        },
                        "StartUV1Random": {
                            "x": 0,
                            "y": 0
                        },
                        "EndUV1": {
                            "x": 0.96,
                            "y": 1
                        },
                        "EndUV1Random": {
                            "x": 0,
                            "y": 0
                        }
                    },
                    "Matrix": None,
                    "ParticleSize": None,
                    "Rotate": {
                        "StartRotate": -60,
                        "StartRotateRandom": 20,
                        "EndRotate": -60,
                        "EndRotateRandom": 20
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": None,
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": None,
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": None,
                    "AdvMultiTexCoordsStep": {
                        "List": [
                            {
                                "Time": 0.041666668,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.04,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.08,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.083333336,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.08,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.12,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.125,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.12,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.16,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.16666667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.16,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.19999999,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.20833333,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.19999999,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.24,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.25,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.24,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.28,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.29166666,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.28,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.32,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.33333334,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.32,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.35999998,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.375,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.35999998,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.39999998,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.41666666,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.39999998,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.44,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.45833334,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.44,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.48,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.5,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.48,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.52,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.5416667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.52,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.56,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.5833333,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.56,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.59999996,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.625,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.59999996,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.64,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.6666667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.64,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.68,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.7083333,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.68,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.71999997,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.75,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.71999997,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.76,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.7916667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.76,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.79999995,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.8333333,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.79999995,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.84,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.875,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.84,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.88,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.9166667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.88,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.91999996,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            }
                        ]
                    }
                }
            ]
        }
    },
    "firewheel": {
        "ParticleStandard": {
            "Flags": 3,
            "Emitters": [
                {
                    "ParticlePropsId": 12368,
                    "EmitterPropsId": 21616,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 200,
                    "EmitterStandard": {
                        "Seed": 2,
                        "MaxParticles": 200,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 4.378521,
                            "y": 4.378521,
                            "z": 1.6235573
                        },
                        "TimeBetweenEmissions": 0,
                        "TimeBetweenEmissionsRandom": 0,
                        "NumParticlesPerEmission": 1,
                        "NumParticlesPerEmissionRandom": 0,
                        "InitialVelocity": 0.67441154,
                        "InitialVelocityRandom": 1.3488231,
                        "ParticleLife": 1.3333334,
                        "ParticleLifeRandom": 1.3333334,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": 0.1348823
                        },
                        "InitialDirectionRandom": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "ParticleSize": {
                            "x": 63.71852,
                            "y": 63.71853
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 6.0264154e-30,
                                "y": 1.285705e-39
                            },
                            {
                                "x": 7.35047e-40,
                                "y": 6.5549e-34
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "firewheel",
                            "textureAlpha": "",
                            "FilterAddressing": {
                                "FilterMode": "Linear_MipMap_Linear",
                                "AddressModeU": "Wrap",
                                "AddressModeV": "Wrap"
                            },
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 251.00002,
                            "green": 252.00002,
                            "blue": 198.00002,
                            "alpha": 76.5
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 251.00002,
                            "green": 252.00002,
                            "blue": 198.00002,
                            "alpha": 0
                        },
                        "EndColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        }
                    },
                    "TextureCoordinates": None,
                    "Matrix": None,
                    "ParticleSize": None,
                    "Rotate": {
                        "StartRotate": 0,
                        "StartRotateRandom": 0,
                        "EndRotate": 3600.0002,
                        "EndRotateRandom": 300
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": {
                        "Radius": 10.946303,
                        "RadiusGap": 0,
                        "UseSphereEmission": False
                    },
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": None,
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": None,
                    "AdvMultiTexCoordsStep": None
                }
            ]
        }
    },
}
