// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import {Script} from "forge-std/Script.sol";
import {TestTarget} from "../src/TestTarget.sol";

contract DeployTestTarget is Script {
    function run() external returns (TestTarget testTarget) {
        vm.startBroadcast();

        testTarget = new TestTarget();

        vm.stopBroadcast();
    }
}
