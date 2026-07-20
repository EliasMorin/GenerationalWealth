"use client";

import React, { useState, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";

function NodeNetwork() {
  const pointsCount = 500;
  const maxDistance = 3.5;
  const groupRef = useRef<THREE.Group>(null);
  const pointsRef = useRef<THREE.Points>(null);

  // Store initial positions to animate them
  const [{ positions, linesIndices, initialPositions }] = useState(() => {
    const pos = new Float32Array(pointsCount * 3);
    const initialPos = new Float32Array(pointsCount * 3);
    for (let i = 0; i < pointsCount; i++) {
      const x = (Math.random() - 0.5) * 30;
      const y = (Math.random() - 0.5) * 20;
      const z = (Math.random() - 0.5) * 15 - 5;
      
      pos[i * 3] = x;
      pos[i * 3 + 1] = y;
      pos[i * 3 + 2] = z;
      
      initialPos[i * 3] = x;
      initialPos[i * 3 + 1] = y;
      initialPos[i * 3 + 2] = z;
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
    return { positions: pos, linesIndices: new Uint16Array(indices), initialPositions: initialPos };
  });

  useFrame((state) => {
    const time = state.clock.getElapsedTime();
    
    if (groupRef.current) {
      groupRef.current.rotation.y = time * 0.05;
      groupRef.current.rotation.x = Math.sin(time * 0.2) * 0.1;
    }

    // Dynamic wave animation for the points
    if (pointsRef.current) {
      const positions = pointsRef.current.geometry.attributes.position.array as Float32Array;
      for (let i = 0; i < pointsCount; i++) {
        const x = initialPositions[i * 3];
        const z = initialPositions[i * 3 + 2];
        // Wavy vertical motion
        positions[i * 3 + 1] = initialPositions[i * 3 + 1] + Math.sin(time + x * 0.2 + z * 0.2) * 1.5;
      }
      pointsRef.current.geometry.attributes.position.needsUpdate = true;
    }
  });

  return (
    <group ref={groupRef}>
      <points ref={pointsRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[positions, 3]}
          />
        </bufferGeometry>
        <pointsMaterial 
          color="#ffffff" 
          size={0.12} 
          transparent 
          opacity={0.9} 
          sizeAttenuation={true} 
          blending={THREE.AdditiveBlending}
        />
      </points>
      <lineSegments>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[positions, 3]}
          />
          <bufferAttribute
            attach="index"
            args={[linesIndices, 1]}
          />
        </bufferGeometry>
        <lineBasicMaterial 
          color="#3b82f6" 
          transparent 
          opacity={0.4} 
          blending={THREE.AdditiveBlending}
        />
      </lineSegments>
    </group>
  );
}

export function Abstract3DObject() {
  return (
    <div className="absolute inset-0 w-full h-full pointer-events-none">
      <Canvas camera={{ position: [0, 0, 12], fov: 60 }} gl={{ alpha: true, antialias: true }}>
        <fog attach="fog" args={["#000000", 5, 25]} />
        <ambientLight intensity={1} />
        <NodeNetwork />
      </Canvas>
    </div>
  );
}
