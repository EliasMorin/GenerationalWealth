"use client";

import React, { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Sphere, MeshDistortMaterial, Float, Environment, Edges } from "@react-three/drei";
import * as THREE from "three";

function AbstractShape() {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.x = state.clock.getElapsedTime() * 0.2;
      meshRef.current.rotation.y = state.clock.getElapsedTime() * 0.3;
    }
  });

  return (
    <Float speed={2} rotationIntensity={1} floatIntensity={2}>
      <mesh ref={meshRef}>
        <icosahedronGeometry args={[1.5, 1]} />
        <meshStandardMaterial 
          color="#3b82f6" 
          wireframe 
          transparent
          opacity={0.3}
        />
        <Edges
          scale={1.05}
          threshold={15}
          color="#60a5fa"
        />
      </mesh>
      
      {/* Inner glowing core */}
      <Sphere args={[0.8, 32, 32]}>
        <MeshDistortMaterial
          color="#1e3a8a"
          envMapIntensity={1}
          clearcoat={1}
          clearcoatRoughness={0.1}
          metalness={0.8}
          roughness={0.2}
          distort={0.4}
          speed={3}
        />
      </Sphere>
    </Float>
  );
}

export function Abstract3DObject() {
  return (
    <div className="w-full h-full min-h-[400px] md:min-h-[500px] relative">
      <Canvas camera={{ position: [0, 0, 5], fov: 45 }}>
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 5]} intensity={1.5} />
        <directionalLight position={[-10, -10, -5]} intensity={0.5} color="#3b82f6" />
        <AbstractShape />
        <Environment preset="city" />
      </Canvas>
    </div>
  );
}
