"use client";

import React, { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";

function NodeNetwork() {
  const pointsCount = 300;
  const maxDistance = 2.5;
  const groupRef = useRef<THREE.Group>(null);

  const { positions, linesIndices } = useMemo(() => {
    const pos = new Float32Array(pointsCount * 3);
    for (let i = 0; i < pointsCount; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 20;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 20;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 10 - 5; // Push slightly back
    }
    
    const indices = [];
    for (let i = 0; i < pointsCount; i++) {
      for (let j = i + 1; j < pointsCount; j++) {
        const dx = pos[i * 3] - pos[j * 3];
        const dy = pos[i * 3 + 1] - pos[j * 3 + 1];
        const dz = pos[i * 3 + 2] - pos[j * 3 + 2];
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (dist < maxDistance) {
          indices.push(i, j);
        }
      }
    }
    return { positions: pos, linesIndices: new Uint16Array(indices) };
  }, []);

  useFrame((state) => {
    if (groupRef.current) {
      groupRef.current.rotation.y = state.clock.getElapsedTime() * 0.03;
      groupRef.current.rotation.x = state.clock.getElapsedTime() * 0.01;
    }
  });

  return (
    <group ref={groupRef}>
      <points>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            count={pointsCount}
            array={positions}
            itemSize={3}
          />
        </bufferGeometry>
        <pointsMaterial color="#60a5fa" size={0.06} transparent opacity={0.6} sizeAttenuation={true} />
      </points>
      <lineSegments>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            count={pointsCount}
            array={positions}
            itemSize={3}
          />
          <bufferAttribute
            attach="index"
            count={linesIndices.length}
            array={linesIndices}
            itemSize={1}
          />
        </bufferGeometry>
        <lineBasicMaterial color="#1e3a8a" transparent opacity={0.25} />
      </lineSegments>
    </group>
  );
}

export function Abstract3DObject() {
  return (
    <div className="absolute inset-0 w-full h-full pointer-events-none">
      <Canvas camera={{ position: [0, 0, 8], fov: 60 }} gl={{ alpha: true }}>
        <fog attach="fog" args={["#000000", 5, 20]} />
        <ambientLight intensity={0.5} />
        <NodeNetwork />
      </Canvas>
    </div>
  );
}
